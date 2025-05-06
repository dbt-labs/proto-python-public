import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

package_name = "dbtlabs_proto_public"
package_version = "v1.0.282"

setuptools.setup(
    name=package_name,
    version=package_version,
    author="dbt Labs",
    author_email="support@dbtlabs.com",
    description="Prototypes for the event bus.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dbt-labs/proto-python-public",
    packages=setuptools.find_namespace_packages(),
    package_data={"": ["*.pyi", "py.typed"]},
    install_requires=["protobuf>=3.17.1"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
