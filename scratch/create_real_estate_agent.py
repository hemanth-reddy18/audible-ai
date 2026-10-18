import sqlite3
import json
import uuid
from datetime import datetime

def create_or_update_real_estate_agent():
    con = sqlite3.connect('audible.db')
    cur = con.cursor()

    workflow_name = "Bridget — Real Estate Customer Support"
    system_prompt = (
        "You are Bridget, a warm, professional, and knowledgeable Customer Support Specialist at Premier Real Estate. "
        "You are running 100% locally on the Audible AI voice platform. "
        "Your mission is to help callers with: "
        "1. Inquiring about residential and commercial real estate, rental listings, single-family homes, and investment properties. "
        "2. Property details, pricing (including listings around $100k, luxury estates, and rental units), square footage, neighborhood amenities, and school ratings. "
        "3. Scheduling in-person or virtual property walkthroughs and viewings. "
        "4. Answering questions in any custom language or preference the caller requests. "
        "5. Providing accurate, conversational assistance without using technical jargon. "
        "Always speak concisely (1 to 2 spoken sentences per turn), warmly, and naturally."
    )
    greeting = "Hello! Thank you for calling Premier Real Estate. My name is Bridget. How can I assist you with your property search or inquiry today?"

    workflow_definition = {
        "nodes": [
            {
                "id": "start",
                "type": "startCall",
                "position": {"x": 250, "y": 100},
                "data": {
                    "is_start": True,
                    "name": "Bridget (Real Estate Specialist)",
                    "allow_interrupt": True,
                    "add_global_prompt": False,
                    "greeting_type": "text",
                    "greeting": greeting,
                    "prompt": system_prompt
                }
            },
            {
                "id": "end",
                "type": "endCall",
                "position": {"x": 250, "y": 350},
                "data": {
                    "is_end": True,
                    "name": "Conclude Call",
                    "allow_interrupt": False,
                    "add_global_prompt": False,
                    "prompt": "Warmly thank the caller for contacting Premier Real Estate, confirm any follow-up steps, and wish them a wonderful day."
                }
            }
        ],
        "edges": [
            {
                "id": "start-to-end",
                "source": "start",
                "target": "end",
                "data": {
                    "label": "Conclude Call",
                    "condition": "When the user expresses they have received all the information they need and says goodbye."
                }
            }
        ]
    }

    definition_json_str = json.dumps(workflow_definition)
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')

    # Check if workflow with name exists
    existing = cur.execute("SELECT id FROM workflows WHERE name = ?", (workflow_name,)).fetchone()
    
    if existing:
        wf_id = existing[0]
        print(f"Updating existing workflow ID: {wf_id}")
        cur.execute("""
            UPDATE workflows 
            SET workflow_definition = ?, status = 'active'
            WHERE id = ?
        """, (definition_json_str, wf_id))
    else:
        wf_uuid = str(uuid.uuid4())
        print(f"Creating new workflow: {workflow_name}")
        cur.execute("""
            INSERT INTO workflows (workflow_uuid, user_id, organization_id, name, status, workflow_definition, template_context_variables, call_disposition_codes, workflow_configurations, created_at, released_definition_id)
            VALUES (?, 1, 1, ?, 'active', ?, '{}', '{"disposition_codes": ["user_hangup"]}', '{}', ?, NULL)
        """, (wf_uuid, workflow_name, definition_json_str, now))
        wf_id = cur.lastrowid
        print(f"Created workflow ID: {wf_id}")

    # Create published workflow definition
    # Check max version number
    max_ver_row = cur.execute("SELECT MAX(version_number) FROM workflow_definitions WHERE workflow_id = ?", (wf_id,)).fetchone()
    next_ver = (max_ver_row[0] or 0) + 1

    cur.execute("""
        INSERT INTO workflow_definitions (workflow_hash, workflow_json, workflow_id, is_current, created_at, status, version_number, published_at, extra_metadata, workflow_configurations, template_context_variables)
        VALUES (NULL, ?, ?, 1, ?, 'published', ?, ?, '{}', '{}', '{}')
    """, (definition_json_str, wf_id, now, next_ver, now))
    def_id = cur.lastrowid
    print(f"Created published workflow definition ID: {def_id} (version {next_ver})")

    # Update workflow to point to released_definition_id
    cur.execute("UPDATE workflows SET released_definition_id = ? WHERE id = ?", (def_id, wf_id))

    con.commit()
    con.close()
    print("SUCCESS: Real Estate Customer Support Agent (Bridget) created and published!")

if __name__ == '__main__':
    create_or_update_real_estate_agent()
