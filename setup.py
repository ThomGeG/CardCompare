from setuptools import setup, find_packages

setup(
    name='CardCompare',
    version='1.0.0',
    description='A price comparison tool for the budget conscious Australian collector',
    url='https://github.com/ThomGeG/CardCompare',

    packages=find_packages(),

    python_requires='>=3.5',
    install_requires=['requests'],
)
