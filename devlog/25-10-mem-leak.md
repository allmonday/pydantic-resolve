# Memory Leak Investigation

        
using `contextvars` in function instead of top-level of module may cause memory leak.

```python
self.ancestor_list = contextvars.ContextVar('ancestor_list', default=[])`
```


## Solution

replace `contextvars` with normal self-implemented context management.