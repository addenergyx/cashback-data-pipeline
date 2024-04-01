from setuptools import setup

setup(
    name="glue_python_shell_module",
    version="0.1",
    install_requires=[
        "pyarrow",
        "s3fs",
        "pyspark",
        "pandas"
    ]
)
