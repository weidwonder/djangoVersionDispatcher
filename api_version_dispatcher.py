#-*-coding: utf-8 -*-
# created on 2015-12-11
#######################################################
#                  版本分发器 0.1
# 基本思路: 不改变url路径, 通过客户端发过来的request来区分版本
# 使用分发器伪装原来的类, 在进入dispatch方法的时候进行对应版本的
# 分发, 即创建对应版本实例 然后调用view的dispatch方法. 同一个view
# 的不同版本将保存在他们对应的分发器的属性中.
########################################################
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.decorators import classonlymethod
from django.views.generic import View

DEFAULT_VERSION = ''

def is_func(target):
    return hasattr(target, 'func_dict')

def is_view(target):
    return isinstance(target, type) and View in target.__mro__

# TODO 接口

##########################################################
#
#     自定义部分
#
##########################################################


def get_version_via_req(request):
    """
    [- 自定义] 获取request中包含的版本号信息.用户可以自定义此方法
    :param request: 请求对象(Request)
    :return: 版本号(str)
    """
    return request.META.get('HTTP_VERSION', DEFAULT_VERSION)

def find_closest_version(version, ver_list):
    """
    [- 自定义] 从ver_list中获取在version版本之前离version最近的版本. 用户必须自定义
    :return: 指定的version(type(version))
    """
    return version

def handle_version_error(error):
    """
    [- 自定义] 当版本错误的时候进行的操作
    :param error: 版本错误时的信息
    :return: 返回的字符串(str)
    """
    print error
    return 'Version_number error!'


class NoVersionMatchException(Exception):
    """ 版本不匹配错误
    """
    def __init__(self):
        super(NoVersionMatchException, self).__init__('Can\'t find a View matching this version.')

class SameVersionException(Exception):
    """ 版本重复错误
    """
    def __init__(self):
        super(SameVersionException, self).__init__('Same version of this view has already defined.')


#####################################################################
#
#    功能部分
#
#####################################################################


class VersionDispatcher:
    """ View 版本分发器
    """

    __version_view_dict__ = {}

    CLASS_TYPE = 'class_type'
    FUNC_TYPE = 'func_type'
    VIEW_TYPES = (CLASS_TYPE, FUNC_TYPE)
    __get_version = staticmethod(get_version_via_req)
    __find_version = staticmethod(find_closest_version)
    __handle_version_error = staticmethod(handle_version_error)

    def __init__(self, *args, **kwargs):
        # super(VersionDispatcher, self).__init__(**kwargs)
        self.kwargs = kwargs

    def dispatch(self, request, *args, **kwargs):
        """ 复写view的分发函数
        :param request: request请求(Request)
        :return: 分发后的结果
        """
        try:
            version = self.__get_version(request)
            view_type, real_view = self.__get_real_view(version)
            if view_type == self.CLASS_TYPE:
                return real_view(**self.kwargs).dispatch(request, *args, **kwargs)
            else:
                return real_view(request, **kwargs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = self.__handle_version_error(e)
            return HttpResponse(simplejson.dumps(error_msg),
                            mimetype='application/json')

    def __get_real_view(self, version):
        """ 获取真正对应版本的View class
        :param version: 版本号(str)
        :param view_name: view名(str)
        :return: 对应版本的class(type)
        :except:
            NoVersionMatchException 没有找到对应版本
        """
        version = self.__find_version(version, self.__version_view_dict__.keys())
        view_type, version_view = self.__version_view_dict__.get(version, (None, None))
        if not version_view or not (is_func(version_view) or is_view(version_view)):
            raise NoVersionMatchException()
        return view_type, version_view

    @classonlymethod
    def add_version_view(cls, version, view):
        """ 增加版本
        :param version: 对应版本
        :param view: 对应view
        :except:
            ValueError view 类型错误
            SameVersionException 相同版本错误
        """
        if cls.__version_view_dict__.get(version) is None:
            if is_func(view):
                view_type = cls.FUNC_TYPE
            elif is_view(view):
                view_type = cls.CLASS_TYPE
            else:
                raise ValueError('View is not a valid class or functional django view.')
            cls.__version_view_dict__[version] = (view_type, view)
        else:
            raise SameVersionException()


def version(ver_num):
    """ 版本装饰器, 生成一个分发器代替被装饰的view, 进行分发操作, 原先的view被保存在分发器的字典属性中
    :param ver_num: 版本号(str)
    :return: 分发器, 与被装饰的view同名
    """
    def view_wrapper(view):
        view_name = view.__name__
        dispatcher = globals().get(view_name)
        if not dispatcher:
            # 添加dispatcher
            dispatcher = type(view_name, (VersionDispatcher, View), {})
            global dispatcher

        if hasattr(ver_num, '__iter__'):
            for ver in ver_num:
                dispatcher.add_version_view(ver, view)
        else:
            dispatcher.add_version_view(ver_num, view)
        return dispatcher
    return view_wrapper


if __name__ == '__main__':
    @version('1')
    class A(View):
        def dispatch(request, *args, **kwargs):
            print 1

    @version('2')
    class A(View):
        def dispatch(request, *args, **kwargs):
            print 2
    @version('3')
    def A(request, *args, **kwargs):
        print 5
    request = type('req', (object, ), {'GET': {}})()
    request.GET['version'] = '2'
    print A().dispatch(request)