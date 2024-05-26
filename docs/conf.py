import datetime

from ytpb._version import __version__


project = "Ytpb"
author = "Maxim Stolyarchuk"
copyright = f"{datetime.date.today().year}, Maxim Stolyarchuk"
version = __version__
release = version

templates_path = ["_templates"]

html_sidebars = {
    "**": [
        "sidebarintro.html",
        "navigation.html",
        "searchbox.html",
    ]
}

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_toolbox.collapse",
    "myst_parser",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

autosectionlabel_prefix_document = True
suppress_warnings = ["autosectionlabel.*"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "autoclass_content": "both",
}

autodoc_preserve_defaults = True
autodoc_inherit_docstrings = True
autodoc_member_order = "bysource"

napoleon_google_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_rtype = False
napoleon_use_ivars = False

html_theme = "alabaster"
html_theme_options = {
    "fixed_sidebar": True,
}
