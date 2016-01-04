# djangoVersionDispatcher
## Introduction
Django Version Dispatcher is a wrapper of django app restful apis. You can use it to wrap a view and specify a version this view is mapping. When a http request coming with a specific version number, then dispatcher will be searching the biggest version of equal to or small than the version in http request.

## Current Version
> 0.1.0

## Using It

* wrap your api view under the `@version`wrapper, and give it a specific app_name and a version number.
* your urls config is as usual.
* `@version()`is considered to be a default version(0.0.0), if there is no version number in http header, then dispatcher will dispatch request to this version.
``` python
## views.py
@version()                   # this is a default version.
class AnApiView(View):
    pass

@version('app_name 1.2.0')
class AnApiView(View):
    pass

@version('app_name 3.0.1')
class AnApiView(View):
    pass

# urls.py
urls = [
    url(r'^your/url/$', AnApiView.as_view()),
]
```

## Caution
If your view inhert another view using version dispatching. You should specify which version it inhert from.
``` python
@version()                   # this is a default version.
class AnApiView(View):
    pass

@version('app_name 1.2.0')
class AnApiView(View):
    pass

@version('app_name 3.0.1')
class AnApiView(AnApiView.version())):    # this view inhert from the first view.
    def some_method():
        pass

@version('app_name 7.0.1')
class AnApiView(AnApiView.version('app_name 3.0.1')):
    def some_method():
        # super method should specify version too.
        super(AnApiView.version('app_name 7.0.1'), self).some_method()