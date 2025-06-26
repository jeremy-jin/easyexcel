from openpyxl import Workbook
from openpyxl.cell.text import InlineFont
from openpyxl.cell.rich_text import TextBlock, CellRichText
red = InlineFont(color='00FF0000', b=True)
rich_string1 = CellRichText(
    [
        'When the color ',
        TextBlock(red, 'red'),
        ' is used, you can expect ',
        TextBlock(red, 'danger')
    ]
)

print("##", rich_string1)

wb = Workbook()
ws = wb.active

cell = ws.cell(row=1, column=1, value=rich_string1)

wb.save("example.xlsx")