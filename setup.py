import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

package_name = "dbt-protos"
package_version = "v1.0.335"

setuptools.setup(
    name=package_name,
    version=package_version,
    author="dbt Labs, Inc.",
    author_email="info@dbtlabs.com",
    description="Public proto bindings for dbt",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dbt-labs/proto-python-public",
    packages=setuptools.find_namespace_packages(),
    package_data={"": ["*.pyi", "py.typed"]},
    install_requires=["protobuf>=3.17.1"],
    license="Apache-2.0",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
    ],
    python_requires=">=3.6",
)
