# Memory Leak Investigation

        
if contextvars holds reference gc will not work.

at end of each `_traverse` reset function should be invoked to clean the references.

```python
self.ancestor_list = contextvars.ContextVar('ancestor_list', default=[])`
```


## Solution

~~replace `contextvars` with normal self-implemented context management.~~

return reset function and call it at end of `_traverse`
```python
    def _prepare_parent(self, node: object):
        if not self.parent_contextvars.get('parent'):
            self.parent_contextvars['parent'] = contextvars.ContextVar('parent')
        token = self.parent_contextvars['parent'].set(node)
        return lambda : self.parent_contextvars['parent'].reset(token)
```