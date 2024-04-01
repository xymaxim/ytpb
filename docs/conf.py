import datetime

project = "Ytpb"
copyright = f"{datetime.date.today().year}, Maxim Stolyarchuk"
author = "Maxim Stolyarchuk"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.napoleon",
    "sphinx_toolbox.collapse",
]

autosectionlabel_prefix_document = True
suppress_warnings = ["autosectionlabel.*"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "autoclass_content": "both",
}

napoleon_google_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_rtype = False
napoleon_use_ivars = False

html_theme = "alabaster"
html_theme_options = {
    "fixed_sidebar": True,
}
