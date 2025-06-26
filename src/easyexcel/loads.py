import re
from abc import ABCMeta

from openpyxl.reader.excel import load_workbook
from openpyxl.workbook import Workbook

from .utils import CollectionProxy, serialize_dict


class BaseSheet:
    SHEET_NAME = None
    FIELDS_IN_EXCEL = None

    # Excel中从第几行开始是有效的数据
    FIRST_ROW_OF_REAL_DATA = 2
    START_COLUMN_NUMBER = 0

    probable_transforms = {}

    def __init__(self, wb: Workbook, first_row_of_real_data: int = None):
        self.wb = wb
        self.first_row_of_real_data = (
            first_row_of_real_data or self.FIRST_ROW_OF_REAL_DATA
        )
        self.titles = []
        self.data = []

    def get_sheet(self):
        sheet = None
        try:
            sheet = self.wb[self.SHEET_NAME]
        except KeyError:
            pass

        return sheet

    def load_excel_title(self, sheet):
        first_row = None
        for row in sheet.rows if sheet else []:
            first_row = row
            break

        self.titles = (
            self.make_row_data(first_row, value_to_string=True)[
                : len(self.FIELDS_IN_EXCEL)
            ]
            if first_row
            else []
        )

    def make_row_data(self, row, start=0, value_to_string=False):
        def serialize_value(value):
            return (
                str(value).strip() if value_to_string and value is not None else value
            )

        compiler = re.compile(r"\d+")
        fields_length = len(self.FIELDS_IN_EXCEL)
        row_data = [
            serialize_value(r_field.value) for r_field in row[start:fields_length]
        ]
        if all(map(lambda x: not x, row_data)):
            return None

        row_data.append(re.findall(compiler, row[0].coordinate)[0])
        return row_data

    def make_serialize_data(self, data):
        for field, transform in self.probable_transforms.items():
            data[field] = transform.to_string(data[field])

        return serialize_dict(data)

    def load_excel_data(self, sheet):
        fields = [
            *list(self.FIELDS_IN_EXCEL.keys())[self.START_COLUMN_NUMBER :],
            "row_number",
        ]

        for row in (
            sheet.iter_rows(min_row=self.first_row_of_real_data) if sheet else []
        ):
            row_data = self.make_row_data(row, start=self.START_COLUMN_NUMBER)
            # 检查所有字段是否为空，为空的数据跳过
            if not row_data:
                break

            self.data.append(self.make_serialize_data(dict(zip(fields, row_data))))

    def load(self):
        sheet = self.get_sheet()
        self.load_excel_title(sheet)
        self.load_excel_data(sheet)


class BaseLoadExcelHandler(metaclass=ABCMeta):
    SHEETS = []

    def __init__(self, excel_file):
        self.excel_file = excel_file
        self.wb = load_workbook(self.excel_file, data_only=True)
        self.sheets = self.register_sheets()

    def register_sheets(self):
        sheets = []
        for sheet in self.SHEETS:
            obj = sheet(self.wb)
            obj.processor = self
            sheets.append(obj)
        return sheets

    def load(self):
        CollectionProxy(self.sheets).load()

    def get_result(self):
        res_data = {}
        for sheet in self.sheets:
            if sheet.SHEET_NAME not in self.wb.sheetnames:
                continue

            res_data[sheet.SHEET_NAME] = {
                "titles": sheet.titles,
                "data": sheet.data,
            }

        return res_data

    def is_template_available(self):
        for sheet in self.sheets:
            if (
                sheet.SHEET_NAME not in self.wb.sheetnames
                or list(sheet.FIELDS_IN_EXCEL.values()) != sheet.titles
            ):
                return False

        return True
