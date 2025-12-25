from setuptools import setup, find_packages

setup(
    name='udown',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
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
