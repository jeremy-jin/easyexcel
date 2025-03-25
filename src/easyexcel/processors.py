from .utils import CollectionProxy


class BaseProcessor(object):
    OBJECT_LIST = []

    def __init__(self, data, validate=False, save=False, *args, **kwargs):
        self.data = data
        self.object_list = []
        self.validate = validate
        self.save = save

        self._init_object_list()

    def _init_object_list(self):
        for attr_name, o in self.OBJECT_LIST:
            instance = o(self.data)
            setattr(self, attr_name, instance)
            instance.processor = self
            self.object_list.append(instance)

    def run_process(self):
        self.load_data()
        self.load_config()
        if self.validate:
            self.inspect_global_settings()
            self.inspect_data()

        if self.save:
            if not self.has_errors():
                try:
                    self.load_config()
                    self.save_data()
                except Exception as e:
                    self.rollback()
                    raise e

    def load_data(self):
        CollectionProxy(self.object_list).load()

    def load_config(self):
        CollectionProxy(self.object_list).load_config()

    def inspect_global_settings(self):
        pass

    def inspect_data(self):
        CollectionProxy(self.object_list).validate()

    def save_data(self):
        CollectionProxy(self.object_list).save()

    def rollback(self):
        CollectionProxy(self.object_list).rollback()

    def has_errors(self):
        is_errors = False
        for o in self.object_list:
            if o.has_errors():
                is_errors = True
                break

        return is_errors

    def get_result(self):
        res = {}
        for o in self.object_list:
            res[o.DATA_NAME] = {
                "titles": o.titles,
                "data": o.get_result(),
            }

        return res
