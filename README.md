# Fuzzy document deduplication

Process ducments using [Amazon Textract](https://aws.amazon.com/textract/) and identify documents to be de-duplicated using [Amazon Comprehend](https://aws.amazon.com/comprehend/) and fuzzy de-duplication using [gensim word mover's distance tool](https://radimrehurek.com/gensim/auto_examples/tutorials/run_wmd.html).


## Application breakdown

1. Extract text from documents using Amazon Textract [multi-page asynchronous function](https://docs.aws.amazon.com/textract/latest/dg/async-analyzing-with-sqs.html)
2. Identify common themes and classify the documents using [Amazon Comprehend topic modeling](https://docs.aws.amazon.com/comprehend/latest/dg/topic-modeling.html)
3. Identify duplicate documents using gensim word mover distance tool
