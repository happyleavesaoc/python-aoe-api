from setuptools import setup, find_packages

setup(
    name='aoeapi',
    version='1.0.0',
    description='Python 3 API for ageofempires.com',
    url='https://github.com/happyleavesaoc/python-aoe-api/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    install_requires=[
        'requests>=2.20.0',
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
