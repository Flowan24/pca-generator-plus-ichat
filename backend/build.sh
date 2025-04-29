#!/bin/bash

# Install system dependencies
apt-get update
apt-get install -y \
    # For magic module (file type detection)
    libmagic1 \
    python3-magic \
    
    # For pytesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    
    # For PDF processing (PyPDFLoader)
    poppler-utils \
    
    # For docx processing (Docx2txtLoader)
    antiword \
    
    # For image processing (PIL)
    libjpeg-dev \
    libpng-dev \
    
    # For UnstructuredFileLoader
    pandoc \
    unrtf \
    
    # For possible dependencies with langchain document processing
    ghostscript \
    build-essential \
    ffmpeg

# Install Python requirements
pip install --upgrade pip
pip install -U langchain-community
pip install -r requirements.txt
