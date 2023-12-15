import functools

def deco(func):
    cache = []
    functools.wraps(func)
    def wrapper():
        if cache:
            print('hit')
            for c in cache:
                yield c
        else:
            for ele in func():
                cache.append(ele)
                yield ele
    return wrapper

@deco
def foo():
    yield 'hello'


for x in foo():
    print(x)

for x in foo():
    print(x)