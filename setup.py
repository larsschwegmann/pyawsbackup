import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyawsbackup", # Replace with your own username
    version="0.0.1",
    author="Lars Schwegmann",
    author_email="info@larsschwegmann.com",
    description="A script to create encrypted folder backups on AWS S3/Glacier/Glacier Deeparchive",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/larsschwegmann/pyawsbackup",
    project_urls={
        "Bug Tracker": "https://github.com/larsschwegmann/pyawsbackup/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.6",
    install_requires=["Click", "clint"],
    entry_points={
        "console_scripts": [
            "pyawsbackup = pyawsbackup:cli"
        ]
    }
)