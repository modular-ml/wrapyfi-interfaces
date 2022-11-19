import setuptools

setuptools.setup(
    name             = 'wrapyfi_interfaces',
    version          = '0.2.0',
    description      = 'Wrapyfi interfaces for communicating with various devices',
    url              = 'https://github.com/modular-ml/wrapyfi-extensions/',
    author           = 'Fares Abawi',
    author_email     = 'fares.abawi@outlook.com',
    maintainer       = 'Fares Abawi',
    maintainer_email = 'fares.abawi@outlook.com',
    packages         = setuptools.find_packages(),
    python_requires  = '>=3.6',
    setup_requires   = ['wrapyfi>=0.4.5']
)
