from setuptools import setup, find_packages

setup(
    name="vit",
    version="0.1.0",
    description="Git for Video Editing — version control timeline metadata, not media files",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "google-generativeai",
        "rich",
        "PySide6",
    ],
    extras_require={},
    entry_points={
        "console_scripts": [
            "vit=vit.cli:main",
        ],
    },
)
