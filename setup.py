"""
Bitcoin On-Chain Predictive Framework
A Machine Learning framework for Bitcoin blockchain analysis
Developed during the CUBO+ program in El Salvador
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="bitcoin-onchain-framework",
    version="0.1.0",
    author="Marcelo Guerra",
    author_email="",
    description="Machine Learning framework for Bitcoin on-chain analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/marchelo23/bitcoin-onchain-framework",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.2",
            "black>=23.9.1",
            "flake8>=6.1.0",
        ],
    },
)
