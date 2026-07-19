Create day2-minibuild/agent.py that solves the SAME task agent-style:               
- Same course client, plain import: from common.llm import chat, STATS              
  (no sys.path tricks).                                                             
- Define exactly three plain Python tool functions (all file paths resolved         
  relative to the script file itself):                                              
    read_notes() -> returns the text of notes.txt (next to the script)              
    count_items(text) -> returns how many action items appear in the given          
  text (implement as a simple line/bullet count)                                    
                                                                                    
    save_output(text) -> writes text to agent_output.txt (next to the script)       
  and returns "saved"                                                               
- System prompt: give the model the GOAL (produce the action-item list with         
  owner/deadline and MISSING flags, the flagged gaps, and a 3-sentence              
  summary), describe the three tools, and tell it to reply each turn with           
  either                                                                            
    ACTION: tool_name(arguments)   or   DONE: <final answer>                        
- Make the reply parsing FORGIVING: models add flourishes. Tolerate case            
  differences (Action:/action:), extra whitespace, conversational preamble          
  before the keyword, and markdown code fences around it. Search for the            
  keyword anywhere in the reply instead of using a rigid startswith check.          
- The loop: send the conversation, parse the reply; on ACTION run that tool         
  and append the result to the conversation; on DONE (or after a maximum of         
  8 turns) stop. If a reply contains neither keyword, append a reminder of          
  the protocol and count it as a turn.                                              
- At the end, print the final answer, the number of turns used, and STATS.