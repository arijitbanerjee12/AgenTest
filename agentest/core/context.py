class Context:
    def __init__(self, data=None):
        object.__setattr__(self, "_store", data or {})

    def __getattr__(self, key):
        store = object.__getattribute__(self, "_store")
        if key in store:
            return store[key]
        val = self.__class__()
        store[key] = val
        return val

    def __setattr__(self, key, value):
        object.__getattribute__(self, "_store")[key] = value

    def __delattr__(self, key):
        store = object.__getattribute__(self, "_store")
        if key in store:
            del store[key]
        else:
            raise AttributeError(key)

    def __getitem__(self, key):
        store = object.__getattribute__(self, "_store")
        if isinstance(key, int):
            self._ensure_list_len(key + 1)
            return store[str(key)]
        if key in store:
            return store[key]
        val = self.__class__()
        store[key] = val
        return val

    def __setitem__(self, key, value):
        store = object.__getattribute__(self, "_store")
        if isinstance(key, int):
            self._ensure_list_len(key + 1)
            store[str(key)] = value
        else:
            store[key] = value

    def __delitem__(self, key):
        store = object.__getattribute__(self, "_store")
        if str(key) in store:
            del store[str(key)]
        elif key in store:
            del store[key]
        else:
            raise KeyError(key)

    def __contains__(self, key):
        store = object.__getattribute__(self, "_store")
        return str(key) in store or key in store

    def __repr__(self):
        store = object.__getattribute__(self, "_store")
        return repr(store)

    def __len__(self):
        store = object.__getattribute__(self, "_store")
        return len(store)

    def _ensure_list_len(self, size):
        store = object.__getattribute__(self, "_store")
        keys = sorted((k for k in store if str(k).lstrip("-").isdigit()), key=int)
        if keys:
            next_idx = max(int(k) for k in keys) + 1
        else:
            existing = [k for k in store if not str(k).lstrip("-").isdigit()]
            for i, k in enumerate(existing):
                store[str(i)] = store.pop(k)
            next_idx = len(existing)
        for i in range(next_idx, size):
            store[str(i)] = self.__class__()

    def to_dict(self):
        store = object.__getattribute__(self, "_store")
        keys = sorted((k for k in store if str(k).lstrip("-").isdigit()), key=int)
        if keys and len(keys) == len(store):
            return [store[k].to_dict() if isinstance(store[k], self.__class__) else store[k] for k in keys]
        return {k: v.to_dict() if isinstance(v, self.__class__) else v for k, v in store.items()}
