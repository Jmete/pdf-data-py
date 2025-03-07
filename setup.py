from setuptools import setup, find_packages

setup(
    name="pdf_data_viewer",
    version="0.2.0",
    description="A PDF viewer with data extraction capabilities",
    author="James Mete",
    packages=find_packages(),
    install_requires=[
        "pymupdf>=1.25.3",
        "pyside6>=6.8.2.1",
        "python-dateutil>=2.8.2",
    ],
    entry_points={
        "console_scripts": [
            "pdf-data-viewer=pdf_data_viewer.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
)
