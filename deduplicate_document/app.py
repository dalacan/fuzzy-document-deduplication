import json
import urllib.parse
import boto3
import os

from gensim.utils import simple_preprocess
from gensim.models.phrases import Phrases, Phraser
from gensim import corpora
from gensim.similarities import Similarity

from nltk.corpus import stopwords
from nltk import download
import nltk
import gensim
import itertools


print('Loading function')

s3 = boto3.resource('s3')

def deduplicate_documents():
    key = 's3://'+os.environ['ModelBucket']+'/'+os.environ['ModelFile']
    model = gensim.models.KeyedVectors.load_word2vec_format(key, binary=True)
    
    # Load files
    sentence_obama = 'Obama speaks to the media in Illinois'
    sentence_president = 'The president greets the press in Chicago'
    
    nltk.data.path.append("/tmp")

    download('stopwords', download_dir = "/tmp")  # Download stopwords list.
    stop_words = stopwords.words('english')
    
    def preprocess(sentence):
        return [w for w in sentence.lower().split() if w not in stop_words]
    
    sentence_obama = preprocess(sentence_obama)
    sentence_president = preprocess(sentence_president)
    
    distance = model.wmdistance(sentence_obama, sentence_president)
    print('distance = %.4f' % distance)
    
    # Run comaparison
    # text_list = []
    
    # for pair in itertools.combinations(text_list, repeat=2):
    #     distance = model.wmdistance(*pair)
    #     print('distance = %.4f' % distance)
    
    # Output
    
    

def lambda_handler(event, context):
    # Get the object from the event and show its content type
    try:
        deduplicate_documents()
        return 1
    except Exception as e:
        print(e)
        
        raise e



