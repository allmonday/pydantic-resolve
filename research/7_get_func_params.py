def _get_args_dict(fn):
    args_names = fn.__code__.co_varnames[:fn.__code__.co_argcount]
    print(args_names)


def foo(name: str, age: int):
    print(name)
    print(age)


_get_args_dict(foo)