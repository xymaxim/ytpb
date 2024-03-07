import datetime

project = "Ytpb"
copyright = f"{datetime.date.today().year}, Maxim Stolyarchuk"
author = "Maxim Stolyarchuk"

extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx_toolbox.collapse",
]

autosectionlabel_prefix_document = True

html_theme = "alabaster"
html_theme_options = {
    "fixed_sidebar": True,
}
