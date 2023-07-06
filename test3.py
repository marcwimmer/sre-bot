import setuptools

setuptools_version = tuple(map(int, setuptools.__version__.split(".")))

print(setuptools.__version__)
print(setuptools_version)