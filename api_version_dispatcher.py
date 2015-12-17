#-*-coding: utf-8 -*-
# created on 2015-12-11
#######################################################
#                  版本分发器 0.1
# 基本思路: 不改变url路径, 通过客户端发过来的request来区分版本
# 使用分发器伪装原来的类, 在进入dispatch方法的时候进行对应版本的
# 分发, 即创建对应版本实例 然后调用view的dispatch方法. 同一个view
# 的不同版本将保存在他们对应的分发器的属性中.
########################################################
from collections import defaultdict

from django.http import HttpResponse
from django.utils import simplejson
from django.utils.decorators import classonlymethod
from django.views.generic import View


tree = lambda : defaultdict(tree)


def is_func(target):
    return hasattr(target, 'func_dict')


def is_view(target):
    return isinstance(target, type) and View in target.__mro__


class VersionException(Exception):
    pass


class NoVersionMatchException(VersionException):
    """ 版本不匹配错误
    """
    def __init__(self, version):
        super(NoVersionMatchException, self).__init__('Can\'t find a View matching version %s.' % version)


class SameVersionException(VersionException):
    """ 版本重复错误
    """
    def __init__(self):
        super(SameVersionException, self).__init__('Same version: "%s" of this view has already defined.' % version)


class NotSameAppException(VersionException):
    """ 不是同一个app错误
    """
    def __init__(self):
        super(NotSameAppException, self).__init__('Not same App. Can\'t compare version.')


class HasDefaultException(VersionException):
    """ 已经有一个默认版本
    """
    def __init__(self, view_name):
        super(HasDefaultException, self).__init__('This Dispatcher: "%s" has already had a default version.' % view_name)

##########################################################
#
#     自定义部分
#
##########################################################
class AppVersion(object):

    app_versions = {

    }

    DEFAULT_VERSION_NAME = '_DEFAULT_VER'
    DEFAULT_VERSION_SEQ = [0]
    DEFAULT_STR = DEFAULT_VERSION_NAME + ' ' + '.'.join(map(str, DEFAULT_VERSION_SEQ))

    def __new__(cls, ver_str):
        if not ver_str:
            ver_str = cls.DEFAULT_STR
        if ver_str in cls.app_versions:
            return cls.app_versions[ver_str]
        else:
            self = super(AppVersion, cls).__new__(cls)
            cls.app_versions[ver_str] = self
            return self

    def __init__(self, ver_str):
        self.is_default = False
        if not ver_str:
            ver_str = self.DEFAULT_STR
            self.is_default = True
        ver_pattern = ver_str.split(' ')
        if len(ver_pattern) != 2:
            raise ValueError('Version string not in format.')
        self.app_name, app_ver_str = ver_pattern
        self.version_seq = map(int, app_ver_str.split('.'))
        self.ver_str = ver_str

    @classmethod
    def get_version_via_req(cls, request):
        """
        [- 自定义] 获取request中包含的版本号信息.用户可以自定义此方法
        :param request: 请求对象(Request)
        :return: 版本号(str)
        """
        return cls(request.META.get('HTTP_APP_VERSION'))

    @classmethod
    def find_closest_version(cls, version, ver_list):
        """
        [- 自定义] 从ver_list中获取在version版本之前离version最近的版本. 用户必须自定义
        :return: 指定的version(type(version))
        """
        if version in ver_list:
            return version
        ver_list = filter(lambda v: v.app_name == version.app_name or v.app_name == cls.DEFAULT_VERSION_NAME, ver_list) + [version]
        ver_list.sort()
        index = ver_list.index(version)
        if index == 0:
            return None
        return ver_list[index - 1]

    @classmethod
    def handle_version_error(cls, error):
        """
        [- 自定义] 当版本错误的时候进行的操作
        :param error: 版本错误时的信息
        :return: 返回的字符串(str)
        """
        return error.message

    def __cmp__(self, v2):
        """ 比较两个版本号
        :param self: 版本号1(AppVersion)
        :param v2: 版本号2(AppVersion)
        :return: v1 >= v2 (bool)
        """
        if self.app_name == v2.app_name or self.DEFAULT_VERSION_NAME in (self.app_name, v2.app_name):
            v1_seq = self.version_seq
            v2_seq = v2.version_seq
            len_dif = len(v1_seq) - len(v2_seq)
            if len_dif > 0:
                v2_seq += [0] * len_dif
            else:
                v1_seq += [0] * len_dif
            for ind in xrange(len(v1_seq)):
                if v1_seq[ind] == v2_seq[ind]:
                    continue
                else:
                    return 1 if v1_seq[ind] > v2_seq[ind] else -1
            return 0
        else:
            raise NotSameAppException()

    @classmethod
    def str2version(cls, version):
        """
        转化字符串到AppVersion对象.
        :param version: 版本号字符串(str)
        :return: 返回AppVersion对象
        """
        if not version:
            version = ''
        if isinstance(version, basestring):
            return cls(version)
        else:
            if isinstance(version, cls):
                return version
            else:
                raise TypeError('`version` must be a instance of AppVersion or a string.')

    def __str__(self):
        return self.ver_str

    def __repr__(self):
        return '< AppVersion ' + self.ver_str + ' >'

    def __hash__(self):
        return hash(self.ver_str)

    def __eq__(self, other):
        other.ver_str == self.ver_str

    def __default__(self):
        return self.is_default


#####################################################################
#
#    功能部分
#
#####################################################################
class VersionDispatcher:
    """ View 版本分发器
    """

    __version_view_dict__ = tree()

    CLASS_TYPE = 'class_type'
    FUNC_TYPE = 'func_type'
    VIEW_TYPES = (CLASS_TYPE, FUNC_TYPE)
    version_class = AppVersion
    has_default = False

    def __init__(self, *args, **kwargs):
        # super(VersionDispatcher, self).__init__(**kwargs)
        self.kwargs = kwargs

    def dispatch(self, request, *args, **kwargs):
        """ 复写view的分发函数
        :param request: request请求(Request)
        :return: 分发后的结果
        """
        try:
            version = self.version_class.get_version_via_req(request)
            view_type, real_view = self.get_version_view(self.__class__.__name__, version)
            if view_type == self.CLASS_TYPE:
                view_instance = real_view(**self.kwargs)
                setattr(view_instance, '__version_dispatcher__', self)
                return view_instance.dispatch(request, *args, **kwargs)
            else:
                return real_view(request, _version_dispatcher=self, *args, **kwargs)
        except VersionException as e:
            import traceback
            traceback.print_exc()
            error_msg = self.version_class.handle_version_error(e)
            return HttpResponse(simplejson.dumps(error_msg),
                            mimetype='application/json')

    def redispatch_to(self, version, request, *args, **kwargs):
        """ 重新分发至指定版本
        :param version: 版本号(AppVersion or str)
        :param request: request请求(Request)
        :return: 分发后的结果
        """
        try:
            version = self.version_class.str2version(version)
            view_type, real_view = self.get_version_view(self.__class__.__name__, version)
            if view_type == self.CLASS_TYPE:
                view_instance = real_view(**self.kwargs)
                setattr(view_instance, '__version_dispatcher__', self)
                return view_instance.dispatch(request, *args, **kwargs)
            else:
                return real_view(request, _version_dispatcher=self, *args, **kwargs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = self.version_class.handle_version_error(e)
            return HttpResponse(simplejson.dumps(error_msg),
                            mimetype='application/json')

    def __call__(self, request, _version='', *args, **kwargs):
        """ 复写函数view
        :param request: request请求(Request)
        :return: 分发后的结果
        """
        try:
            if not _version:
                version = self.version_class.get_version_via_req(request)
            else:
                version = self.version_class.str2version(_version)
            view_type, real_view = self.get_version_view(version)
            if view_type == self.CLASS_TYPE:
                view_instance = real_view(**self.kwargs)
                setattr(view_instance, '__version_dispatcher__', self)
                return view_instance.dispatch(request, *args, **kwargs)
            else:
                return real_view(request, _version_dispatcher=self, *args, **kwargs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = self.version_class.handle_version_error(e)
            return HttpResponse(simplejson.dumps(error_msg),
                            mimetype='application/json')

    @classmethod
    def get_version_view(cls, view_name, version=None):
        """ 获取真正对应版本的View class
        :param version: 版本号(str)
        :param view_name: view名(str)
        :return: 对应版本的class(type)
        :except:
            NoVersionMatchException 没有找到对应版本
        """
        version = AppVersion.str2version(version)
        version = cls.version_class.find_closest_version(version, cls.__version_view_dict__[cls.__name__].keys())
        view_type, version_view = cls.__version_view_dict__[view_name][version] or (None, None)
        if not version_view or not (is_func(version_view) or is_view(version_view)):
            raise NoVersionMatchException(version)
        return view_type, version_view

    @classmethod
    def version(cls, version=None):
        return cls.get_version_view(cls.__name__, version)[1]

    @classonlymethod
    def add_version_view(cls, version, view):
        """ 增加版本
        :param version: 对应版本
        :param view: 对应view
        :except:
            ValueError view 类型错误
            SameVersionException 相同版本错误
        """
        version = AppVersion.str2version(version)
        if version.__default__():
            if cls.has_default:
                raise HasDefaultException(view.__name__)
            cls.has_default = True

        if cls.__version_view_dict__.get(version) is None:
            if is_func(view):
                view_type = cls.FUNC_TYPE
            elif is_view(view):
                view_type = cls.CLASS_TYPE
            else:
                raise ValueError('View is not a valid class or functional django view.')
            setattr(view, 'view_dispatcher', cls)
            cls.__version_view_dict__[view.__name__][version] = (view_type, view)
        else:
            raise SameVersionException()

def version(ver_num="", ver_class=AppVersion):
    """ 版本装饰器, 生成一个分发器代替被装饰的view, 进行分发操作, 原先的view被保存在分发器的字典属性中
    :param ver_num: 版本号(str)
    :return: 分发器, 与被装饰的view同名
    """
    def view_wrapper(view):
        view_name = view.__name__
        dispatcher = type(view_name, (VersionDispatcher, View), {})
        if hasattr(ver_num, '__iter__'):
            for ver in ver_num:
                dispatcher.add_version_view(ver_class(ver), view)
        else:
            dispatcher.add_version_view(ver_class(ver_num), view)
        return dispatcher
    return view_wrapper


if __name__ == '__main__':
    # @version('')
    # class A(View):
    #     def dispatch(request, *args, **kwargs):
    #         print 1

    @version('B 2')
    class A(View):
        def dispatch(request, *args, **kwargs):
            print 2
    @version('C 9.10')
    def A(request, *args, **kwargs):
        print 9.1, '>>>'


    @version('B 2')
    class B(A.version('B 2')):
        def dispatch(request, *args, **kwargs):
            print 2



    @version('C 9.10')
    def B(request, *args, **kwargs):
        print 9.1, '>>>'

    @version(('C 1.1.1', 'B 9.10'))
    def A(request, *args, **kwargs):
        print 9.1
    request = type('req', (object, ), {'GET': {}, 'META': {'HTTP_APP_VERSION': 'B 2.10'}})()
    print A().dispatch(request)
