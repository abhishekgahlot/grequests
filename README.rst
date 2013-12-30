GRequests: Asynchronous Requests
===============================

grequests 0.2.0 with exception_handler, gevent 1.0 compatible 

See https://github.com/kennethreitz/grequests for usage

To suppress warnings
```
grequests.map(rs, exception_handler=lambda *x: True)
```

To handle
```
def eh(p1,p2):
  print h1, h2

grequests.map(rs, exception_handler=eh)
```
