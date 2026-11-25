
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from tinydb import TinyDB, Query
import os
import networkx as nx
import random
from src.protocols.aodv import AODV
from src.protocols.coap import CoAP
from src.metrics.performance import PerformanceMetrics

import requests
import json
import hashlib
import re

app = Flask(__name__)
app.secret_key = 'smart-light-controller-secret-key-2026'
db = TinyDB('db.json')

# Helper functions for password hashing
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed

# Hardcoded demo credentials
DEMO_USERS = {
    'admin': 'admin123',
    'user': 'user123'
}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Login page route
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check demo users first
        if username in DEMO_USERS and DEMO_USERS[username] == password:
            session['username'] = username
            return redirect(url_for('home'))
        
        # Check database users
        User = Query()
        user = db.search(User.username == username)
        if user and verify_password(password, user[0]['password_hash']):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            return redirect(url_for('login_page', error=True))
    
    return render_template('login.html')

# Signup page route
@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        if not username or not email or not password:
            return redirect(url_for('signup_page', error='invalid'))
        
        if len(username) < 3:
            return redirect(url_for('signup_page', error='invalid'))
        
        # Check if username/email already exists
        User = Query()
        existing_user = db.search((User.username == username) | (User.email == email))
        if existing_user:
            return redirect(url_for('signup_page', error='exists'))
        
        # Check demo users
        if username in DEMO_USERS:
            return redirect(url_for('signup_page', error='exists'))
        
        # Check password requirements
        if len(password) < 6 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return redirect(url_for('signup_page', error='invalid'))
        
        if password != confirm_password:
            return redirect(url_for('signup_page', error='invalid'))
        
        # Create new user
        db.insert({
            'username': username,
            'email': email,
            'password_hash': hash_password(password)
        })
        
        return redirect(url_for('signup_page', success=True))
    
    return render_template('signup.html')

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/generate_pattern', methods=['POST'])
def generate_pattern():
    data = request.json
    command = data.get('command', '').strip()

    if not command:
        return jsonify({'indices': []})

    api_key = "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"

    prompt = f"""
You are a function that outputs ONLY a JSON array of integers.

GRID: 10x10 indices 0–99 (row-wise).
User wants a lighting pattern representing: "{command}"

Rules:
- Output ONLY a JSON array like: [0,1,2]
- No text, no explanation, no markdown
"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "liquid/lfm-2.5-1.2b",   # 🔥 NON-thinking model
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )

        res = response.json()
        raw = res["choices"][0]["message"]["content"]

        # 🔥 STRONG extraction: first [...] block
        match = re.search(r'\[[\d,\s]+\]', raw)
        if not match:
            return jsonify({'indices': []})

        indices = json.loads(match.group(0))
        indices = [i for i in indices if 0 <= i <= 99]

        return jsonify({'indices': indices})

    except Exception as e:
        print("Pattern generation error:", e)
        return jsonify({'indices': []})

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/simulation', methods=['GET', 'POST'])
@login_required
def simulation():
    return render_template('simulation.html')

@app.route('/existing_performance')
@login_required
def existing_performance():
    return render_template('existing.html')

@app.route('/proposed_performance')
@login_required
def proposed_performance():
    return render_template('proposed.html')

@app.route('/comparison', methods=['GET', 'POST'])
@login_required
def comparison():
    nodes = 30
    tx_power = 10
    energy = 100
    if request.method == 'POST':
        nodes = request.form.get('nodes', 30, type=int)
        tx_power = request.form.get('tx_power', 10, type=float)
        energy = request.form.get('energy', 100, type=float)
    
    def get_full_metrics(n, tp, e):
        # Helper to get all 5 metrics
        a_proto = AODV(range(n), [])
        c_proto = CoAP(range(n), [])
        
        inp = {'nodes': n, 'tx_power': tp, 'energy': e}
        
        a_m = PerformanceMetrics.calculate(a_proto.get_metrics(inp), inp)
        a_m['path_length'] = round(n * 0.4 + (random.random() * 2), 2)
        a_m['delivery_eff'] = round(70 + (tp * 0.5) + (random.random() * 5), 2)
        
        c_m = PerformanceMetrics.calculate(c_proto.get_metrics(inp), inp)
        c_m['path_length'] = round(n * 0.15 + (random.random() * 1), 2)
        c_m['delivery_eff'] = round(92 + (tp * 0.2) + (random.random() * 2), 2)
        c_m['delivery_eff'] = min(99.8, c_m['delivery_eff'])
        
        return a_m, c_m

    # Current metrics
    aodv_metrics, coap_metrics = get_full_metrics(nodes, tx_power, energy)
    
    # Trends for "Multiple Scenarios" (varying nodes up to user-defined maximum)
    min_nodes = 10
    max_nodes = max(min_nodes + 5, nodes)
    step = max(1, (max_nodes - min_nodes) // 5)
    scenarios = list(range(min_nodes, max_nodes + 1, step))
    # Ensure the last point is exactly max_nodes if not already
    if scenarios[-1] != max_nodes: scenarios.append(max_nodes)
    
    trends = {'labels': scenarios, 'aodv': [], 'coap': []}
    for s in scenarios:
        am, cm = get_full_metrics(s, tx_power, energy)
        trends['aodv'].append(am)
        trends['coap'].append(cm)

    return render_template('comparison.html', 
                         nodes=nodes, 
                         tx_power=tx_power, 
                         energy=energy,
                         aodv=aodv_metrics,
                         coap=coap_metrics,
                         trends=trends)

@app.route('/smart_controller')
@login_required
def smart_controller():
    # Fetch parameters to drive the communication simulation
    nodes = request.args.get('nodes', 30, type=int)
    tx_power = request.args.get('tx_power', 10, type=float)
    return render_template('smart_controller.html', nodes=nodes, tx_power=tx_power, username=session.get('username'))

@app.route('/api/generate_network', methods=['POST'])
def generate_network():
    data = request.json
    num_nodes = int(data.get('nodes', 10))
    
    nodes = list(range(num_nodes))
    edges = []
    # Create a connected-ish graph
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if random.random() < 0.3: # density
                weight = random.uniform(1, 10)
                edges.append((i, j, weight))
    
    # Ensure connectivity for demo
    G = nx.fast_gnp_random_graph(num_nodes, 0.2)
    while not nx.is_connected(G):
        G = nx.fast_gnp_random_graph(num_nodes, 0.2)
    
    nodes_data = [{'id': n, 'x': random.randint(50, 750), 'y': random.randint(50, 450)} for n in G.nodes()]
    edges_data = [{'source': u, 'target': v, 'weight': random.uniform(1, 10)} for u, v in G.edges()]
    
    return jsonify({'nodes': nodes_data, 'edges': edges_data})

def safe_path(x):
    return [int(n) for n in x] if isinstance(x, list) else []


# =====================================================
# API: CALCULATE PATH + METRICS
# =====================================================
@app.route("/api/calculate_path", methods=["POST"])
def calculate_path():
    print("DEBUG: calculate_path called")
    try:
        data = request.json
        if not data or not isinstance(data, dict):
            print("DEBUG: No data or data is not a dict")
            return jsonify({"error": "DEBUG_PATH: No input data"}), 400

        # Build nodes list safely
        raw_nodes = data.get("nodes", [])
        if not isinstance(raw_nodes, list):
            print(f"DEBUG: raw_nodes is not a list: {type(raw_nodes)}")
            raw_nodes = []
        
        nodes = []
        for n in raw_nodes:
            if isinstance(n, dict) and "id" in n:
                try: nodes.append(int(n["id"]))
                except: continue
        
        # Build edges list safely
        raw_edges = data.get("edges", [])
        if not isinstance(raw_edges, list):
            print(f"DEBUG: raw_edges is not a list: {type(raw_edges)}")
            raw_edges = []
            
        edges = []
        for e in raw_edges:
            if isinstance(e, dict) and "source" in e and "target" in e:
                try:
                    edges.append((int(e["source"]), int(e["target"]), float(e.get("weight", 1))))
                except: continue
        
        source = int(data.get("source", 0))
        target = int(data.get("target", 0))

        print(f"DEBUG: nodes={len(nodes)}, edges={len(edges)}, src={source}, dest={target}")

        if source not in nodes or target not in nodes:
            return jsonify({
                "path_aodv": [], "path_coap": [],
                "ch_aodv": [], "ch_coap": [],
                "error": "DEBUG_PATH: Source/Target not in nodes"
            })

        aodv = AODV(nodes, edges)
        coap = CoAP(nodes, edges)

        # Calculate initial paths
        path_aodv = aodv.find_path(source, target)
        path_coap = coap.find_path(source, target)

        # Simulation Logic: AODV should be less efficient than CoAP
        if path_aodv and path_coap and len(path_aodv) <= len(path_coap):
            try:
                # Find all simple paths within a small depth increase
                # This simulates AODV's tendency to not always find the global optimum
                cutoff = len(path_coap) + 5
                all_paths = list(nx.all_simple_paths(aodv.G, source, target, cutoff=cutoff))
                if len(all_paths) > 1:
                    # Pick a path that is longer than CoAP's
                    longer_paths = [p for p in all_paths if len(p) > len(path_coap)]
                    if longer_paths:
                        path_aodv = random.choice(longer_paths)
                    else:
                        path_aodv = max(all_paths, key=len)
            except: 
                pass

        def sanitize(path):
            if not isinstance(path, list): return []
            return [int(n) for n in path]

        return jsonify({
            "path_aodv": sanitize(path_aodv),
            "path_coap": sanitize(path_coap),
            "ch_aodv": sanitize(aodv.select_cluster_heads()),
            "ch_coap": sanitize(coap.select_cluster_heads())
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
