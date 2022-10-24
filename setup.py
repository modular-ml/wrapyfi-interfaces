import setuptools

with open('requirements.txt') as f:
    requirements = f.read().splitlines()


setuptools.setup(
    name             = 'wrapyfi_interaces',
    version          = '0.1.0',
    description      = 'Wrapyfi interfaces for communicating with various devices',
    url              = 'https://github.com/modular-ml/wrapyfi-extensions/',
    author           = 'Fares Abawi',
    author_email     = 'fares.abawi@outlook.com',
    maintainer       = 'Fares Abawi',
    maintainer_email = 'fares.abawi@outlook.com',
    packages         = setuptools.find_packages(),
    install_requires = requirements,
    python_requires='>=3.6',
)
