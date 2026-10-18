import urllib.request
import json

def run_verification():
    print("=== AUDIBLE AI INTEGRATION VERIFICATION ===")

    # 1. Health Check
    req_health = urllib.request.Request("http://localhost:3010/api/v1/health")
    with urllib.request.urlopen(req_health) as resp:
        health_data = json.loads(resp.read().decode())
        print(f"1. GATEWAY HEALTH: HTTP {resp.status} - Status: {health_data.get('status')}")

    # 2. Login
    req_login = urllib.request.Request(
        "http://localhost:3010/api/v1/auth/login",
        data=json.dumps({"email": "ceo@audible.ai", "password": "Audible2026!"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_login) as resp:
        login_data = json.loads(resp.read().decode())
        token = login_data["token"]
        print(f"2. LOGIN SUCCESS: HTTP {resp.status} - Authenticated as {login_data['user']['email']}")

    # 3. Workflows List
    req_wf = urllib.request.Request(
        "http://localhost:3010/api/v1/workflow/fetch?status=active",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_wf) as resp:
        workflows = json.loads(resp.read().decode())
        print(f"3. ACTIVE WORKFLOWS ({len(workflows)} total):")
        for wf in workflows:
            print(f"   - [ID {wf['id']}] {wf['name']} (Status: {wf.get('status')})")

    # 4. Create Run for Bridget (Workflow #2)
    req_run = urllib.request.Request(
        "http://localhost:3010/api/v1/workflow/2/runs",
        data=json.dumps({"mode": "small_webrtc", "name": "AUDIBLE-BRIDGET-VERIFICATION"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req_run) as resp:
        run_data = json.loads(resp.read().decode())
        print(f"4. BRIDGET VOICE RUN INITIALIZED: Run ID {run_data.get('id')} (Keys: {list(run_data.keys())})")

    # 5. Test Ollama inference with Bridget's prompt
    prompt = (
        "You are Bridget, a customer support specialist at Premier Real Estate. "
        "A client asks: 'Hi Bridget, do you have any properties or single family homes around $100k or with custom language support?' "
        "Answer warmly and concisely in 1-2 sentences."
    )
    req_ollama = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({"model": "llama3.2:1b", "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_ollama) as resp:
        llm_data = json.loads(resp.read().decode())
        print(f"5. LOCAL LLM INFERENCE (llama3.2:1b):")
        print(f"   Bridget: \"{llm_data['response'].strip()}\"")

    print("\nALL 5 INTEGRATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_verification()
