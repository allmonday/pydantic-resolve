class A:
    class Config:
        name = 'config'

class B(A):
    name = 'b'

b = B()
print(B.__dict__)  # no Config

a = A()
print(A.__dict__)