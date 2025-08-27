# -- IMPORT --

# import streamlit keys
import streamlit as st

# env import
import os
import glob
from dotenv import load_dotenv

# -- SETUP CONFIGURATION --

# Configure the secrets keys (Streamlit Version)
secrets = st.secrets['general']
OPENROUTER_API_KEY = secrets['OPENROUTER_API_KEY']
MISTRAL_API_KEY = secrets['MISTRAL_API_KEY']
HF_TOKEN = secrets['HF_TOKEN']
PERSIST_PATH = secrets['PERSIST_PATH']

# Multi Query Retrieval setup
N_PARAPHRASES = 3            # number of paraphrases to generate
MAX_MERGED_DOCS = 5          # final docs to return after dedupe
PARAPHRASE_CACHE_SIZE = 512
RETRIEVAL_CACHE_SIZE = 2048