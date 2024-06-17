# Create your views here.

#Import the necessary modules, functions, and information
from django.shortcuts import render
from django.shortcuts import redirect
from ir_app.models import invertedindex
from ir_app.models import documents
from django.contrib import messages
from django.http import HttpResponse
import random
import io
import PyPDF2
from PyPDF2 import PdfReader
import mimetypes
from django.core.files.base import ContentFile
import fitz
import json


from django.shortcuts import render

# Import necessary libraries for preprocessing and search functionality
import re
import json
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
import nltk

nltk.download('punkt')

class Node:
    def __init__(self, doc_id, positions):
        self.doc_id = doc_id
        self.positions = positions
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None

    def insert(self, doc_id, position):
        if self.head is None:
            self.head = Node(doc_id, [position])
            return

        current_node = self.head
        last_node = None

        while current_node:
            if current_node.doc_id == doc_id:
                current_node.positions.append(position)
                return

            last_node = current_node
            current_node = current_node.next

        last_node.next = Node(doc_id, [position])

    def display(self):
        current = self.head
        while current:
            print(f"Doc ID: {current.doc_id}, Positions: {current.positions}")
            current = current.next

def preprocess_documents(documents):
    processed_docs = []
    ps = PorterStemmer()

    for doc in documents:
        cleaned_doc = re.sub(r'[^\w\s]', '', doc).lower()
        tokens = word_tokenize(cleaned_doc)
        stemmed_tokens = [ps.stem(token) for token in tokens]
        processed_docs.append(stemmed_tokens)

    return processed_docs

def linked_to_dict(linked_list):
    current = linked_list.head
    doc_dict = {}
    while current:
        doc_dict[current.doc_id] = current.positions
        current = current.next
    return doc_dict


def find_documents_test(postings, query):
    results_all = []
    valid_docs = []
    final_new_valid = []
    for i, q in enumerate(query):
        new_valid = []
        results = []
        if q[0] in postings:
            for doc_id, positions in postings[q[0]].items():
                if i != 0:
                    if doc_id not in valid_docs:
                        continue
                for pos in positions:
                    if all((term in postings and doc_id in postings[term] and pos+i in postings[term][doc_id]) for i, term in enumerate(q)):
                        new_valid.append(doc_id)
                        results.append((doc_id, pos))
        valid_docs = new_valid
        results_all.append(results)
        final_new_valid = new_valid
    if len(results_all) > 1:
        final_results = []
        for q in results_all:
          good_results = []
          for pair in q:
            if pair[0] in final_new_valid:
                good_results.append(pair)
          final_results.append(good_results)
    else:
        final_results = results_all

    return final_results



def get_binary(request):
    uploaded_file = request.FILES.getlist('files')
    binary_content = []

    #Read binary data of the uploaded file
    file_content = uploaded_file[0].read()
    binary_content.append(file_content)
    #This gets the file type from the uploaded file's name or MIME type
    file_type = uploaded_file[0].name.split('.')[-1] if '.' in uploaded_file[0].name else ''

    #Here we save the file content and type to the database
    ir_app_document = documents(content=file_content, file_type=file_type)
    ir_app_document.save() 
    return binary_content

def get_pos_index():

    invertedindex.objects.all().delete()

    row_count = documents.objects.count()

    corpus = []
    for num in range(row_count):
        file_data = get_object_or_404(documents, pk=num+1)
        doc_id = num+1
        if file_data.file_type == 'txt':
            text = file_data.content.tobytes().decode("utf-8")
        if file_data.file_type == 'pdf':
            pdf_bytes = file_data.content
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PdfReader(pdf_file)
            extracted_text = ""
            for page in pdf_reader.pages:
                #THis extracts text from the current page
                extracted_text += page.extract_text()
            text = extracted_text
            pdf_file.close()
            


        corpus.append(text)


    processed_docs = preprocess_documents(corpus)
    
        

    positional_index = {}
    for doc_id, doc in enumerate(processed_docs):
        for pos, term in enumerate(doc):
            if term not in positional_index:
                positional_index[term] = LinkedList()
            positional_index[term].insert(doc_id+1, pos)

    #THis converts the positional index to dictionary
    positional_index_dict = {term: linked_to_dict(positional_index[term]) for term in positional_index}
    
    pos_inv_index = invertedindex(Index=positional_index_dict)
    pos_inv_index.save()

def file_upload_view(request):
    if request.method == 'POST':
        get_binary(request)
        get_pos_index()
        


        return render(request, 'Homepage_3.html')

    else:
        return render(request, 'Homepage_3.html')



from django.db import connection

def reset_database(request):
    
    documents.objects.all().delete()
    
    with connection.cursor() as cursor:
        cursor.execute("ALTER SEQUENCE ir_app_documents_id_seq RESTART WITH 1;")
    
    invertedindex.objects.all().delete()

    with connection.cursor() as cursor:
        cursor.execute("ALTER SEQUENCE ir_app_invertedindex_id_seq RESTART WITH 1;")

    context = {
        'reset_success_message': "Database reset successful"
    }
    
   
    return render(request, 'Homepage_3.html', context)




def search_results_test(request):
    query = request.GET.get('query')
    if ";" in query:
        query = query.split(";")
        q = query
    else:
        q = []
        q.append(query)
    global q_global
    q_global = q
    global pro_query
    pro_query = preprocess_documents(q)
    inverted_index_entry = invertedindex.objects.first()  

    if inverted_index_entry:
        #Here we access the index column containing the inverted index data
        inverted_index_data = inverted_index_entry.Index


    global results
    results = find_documents_test(inverted_index_data, pro_query)

    
    rel_docs = []
    for doc_pos in results[0]:
        if doc_pos[0] not in rel_docs:
            rel_docs.append(doc_pos[0])
    

    return render(request, 'search_test.html', {'results': rel_docs, "test" : results})
    












from django.shortcuts import render, get_object_or_404
import base64

def display_doc_test(request, doc_id):
    colors =  [
    "#FFFF00",  # Yellow
    "#FF0000",  # Red
    "#00FF00",  # Green
    "#0000FF",  # Blue
    "#00FFFF",  # Cyan
    "#FF00FF",  # Magenta
    "#FFA500",  # Orange
    "#800080",  # Purple
    "#A52A2A",  # Brown
    "#FFC0CB",  # Pink
    "#FFD700",  # Gold
    "#C0C0C0"   # Silver
]
    positions_all = {}
    occurences = {}
    for q , r, a in zip(pro_query, results, q_global):
        count = 0
        len_q = len(q)
        positions = []
        count = 0
        for doc_pos in r:
            if int(doc_pos[0]) == doc_id:
                positions.append(doc_pos[1])
                count += 1
                for i in range(len_q):
                    if i == 0:
                        continue
                    positions.append(doc_pos[1]+i)
        positions_all[a] = positions
        occurences[a] = count
    # Retrieve the documents object from the database
    file_data = get_object_or_404(documents, pk=doc_id)
    
    # Determine the appropriate HTML content based on the file type
    if file_data.file_type == 'pdf':
        pdf_content = file_data.content
        pdf_binary = bytes(pdf_content)
        pdf_base64 = base64.b64encode(pdf_binary).decode('utf-8')
        positions_json = json.dumps(positions_all)
        query = json.dumps(q_global)
        return render(request, 'display_pdf_multi_test.html', {'document': doc_id, 'pdf_content': pdf_base64, 'positions': positions, 'positions_json' : positions_json, 'count': occurences, 'query': query})
    
    elif file_data.file_type == 'txt':
 
        content_txt = file_data.content.tobytes().decode("utf-8")
        content = content_txt.split()
        c_pro = []
        handled = {}


        for pos, color in zip(positions_all.values(), colors):
            pos_list = list(pos)
            for i, term in enumerate(content):
                if i in pos_list:
                    handled[i] = f'<mark style="background-color: {color};">{term}</mark>'

        for i, term in enumerate(content):
            if i in handled:
                c_pro.append(handled[i])
            else:
                c_pro.append(term)
    
        html_content = " ".join(c_pro)
        return render(request, 'display_doc.html', {'document': doc_id, 'html_content': html_content, 'positions': positions_all, 'count': occurences, 'query': q_global})
    
   
























def display_doc(request, doc_id):
    len_q = len(pro_query[0])
    positions = []
    for doc_pos in results:
        if int(doc_pos[0]) == doc_id:
            positions.append(doc_pos[1])
            for i in range(len_q):
                if i == 0:
                    continue
                positions.append(doc_pos[1]+i)

    # Retrieve the documents object from the database
    file_data = get_object_or_404(documents, pk=doc_id)
    
    count = len(positions)
    # Determine the appropriate HTML content based on the file type
    if file_data.file_type == 'pdf':
        pdf_content = file_data.content
        pdf_binary = bytes(pdf_content)
        pdf_base64 = base64.b64encode(pdf_binary).decode('utf-8')
        positions_json = json.dumps(positions)
        return render(request, 'display_pdf_tes_1.html', {'document': doc_id, 'pdf_content': pdf_base64, 'positions': positions, 'positions_json' : positions_json, 'count': count, 'query': q_global})
    
    elif file_data.file_type == 'txt':
 
        content_txt = file_data.content.tobytes().decode("utf-8")
        content = content_txt.split()
        c_pro = []
        for i, term in enumerate(content):
            if i in positions:
                c_pro.append(f'<mark>{term}</mark>')
            else:
                c_pro.append(term)
        html_content = " ".join(c_pro)
        return render(request, 'display_doc.html', {'document': doc_id, 'html_content': html_content, 'positions': positions, 'count': count, 'query': q_global})
    
   

