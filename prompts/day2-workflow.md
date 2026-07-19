Create day2-minibuild/workflow.py. It must be a FIXED PIPELINE, not an agent:       
- Import the course client with a plain: from common.llm import chat, STATS         
  (this just works - the Codespace sets PYTHONPATH; do NOT add sys.path tricks).    
- Read notes.txt from the SAME FOLDER as the script (resolve the path relative      
  to the script file itself, not the current directory).                            
- Make exactly THREE chat() calls, in this fixed order:                             
    1. Extract every action item from the notes as a list of task / owner /         
       deadline. Use "MISSING" when an owner or deadline is absent. Ignore          
       ideas that were explicitly parked.                                           
    2. Given that list, output only the items that have a MISSING owner or deadline.
    3. Given the list and the flags, write a 3-sentence status summary.             
- The Python code decides every step. The model must never choose what happens      
  next. NO loops of any kind, no tools, no retries.                                 
- At the end, print the action-item list, the flags, the summary, and STATS. 

running code face below errors, please fix the code:                                
repo/day2-minibuild $ python3 workflow.py                                           
Traceback (most recent call last):                                                  
  File "/workspaces/collective-assignment-behrouzzzz/common/llm.py", line 77, in    
chat                                                                                
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))                  
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^                   
  File "/usr/lib/python3.11/urllib/request.py", line 216, in urlopen                
    return opener.open(url, data, timeout)                                          
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^                                          
  File "/usr/lib/python3.11/urllib/request.py", line 525, in open                   
    response = meth(req, response)                                                  
               ^^^^^^^^^^^^^^^^^^^                                                  
  File "/usr/lib/python3.11/urllib/request.py", line 634, in http_response          
    response = self.parent.error(                                                   
               ^^^^^^^^^^^^^^^^^^                                                   
  File "/usr/lib/python3.11/urllib/request.py", line 563, in error                  
    return self._call_chain(*args)                                                  
           ^^^^^^^^^^^^^^^^^^^^^^^                                                  
  File "/usr/lib/python3.11/urllib/request.py", line 496, in _call_chain            
    result = func(*args)                                                            
             ^^^^^^^^^^^                                                            
  File "/usr/lib/python3.11/urllib/request.py", line 643, in http_error_default     
    raise HTTPError(req.full_url, code, msg, hdrs, fp)                              
urllib.error.HTTPError: HTTP Error 400: Bad Request                                 
                                                                                    
The above exception was the direct cause of the following exception:                
                                                                                    
Traceback (most recent call last):                                                  
  File "/workspaces/collective-assignment-behrouzzzz/day2-minibuild/workflow.py",   
line 9, in <module>                                                                 
    action_items = chat(                                                            
                   ^^^^^                                                            
  File "/workspaces/collective-assignment-behrouzzzz/common/llm.py", line 89, in    
chat                                                                                
    raise RuntimeError(f"{PROVIDER} rejected the request "                          
RuntimeError: OU LiteLLM Sandbox rejected the request (400):                        
b'{"error":{"message":"Invalid request format: 'str' object has no attribute        
'get'","type":"invalid_request_error","param":null,"code":"400"}}'