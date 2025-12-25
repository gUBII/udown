from pathlib import Path

from setuptools import find_packages, setup


README = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name='udown',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    long_description=README,
    long_description_content_type="text/markdown",
    install_requires=[
        'yt-dlp',
        'click',
        'Flask',
        'certifi',
    ],
    entry_points={
        'console_scripts': [
            'udown = udown.main:cli',
        ],
    },
)
