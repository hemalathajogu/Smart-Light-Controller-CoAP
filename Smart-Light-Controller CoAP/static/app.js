const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

let positions = [];

function generate() {
    const n = Number(document.getElementById("nodes").value);
    positions = [];

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < n; i++) {
        positions.push({
            x: Math.random() * 800 + 50,
            y: Math.random() * 350 + 50
        });
        drawNode(i, "purple");
    }
}

function drawNode(id, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(positions[id].x, positions[id].y, 10, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillText(id, positions[id].x - 4, positions[id].y + 4);
}

function drawEdge(a, b, color) {
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(positions[a].x, positions[a].y);
    ctx.lineTo(positions[b].x, positions[b].y);
    ctx.stroke();
}

function transmit() {
    fetch("/api/calculate_path", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            num_nodes: Number(document.getElementById("nodes").value),
            source: Number(document.getElementById("source").value),
            destination: Number(document.getElementById("destination").value)
        })
    })
    .then(res => res.json())
    .then(data => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        positions.forEach((_, i) => drawNode(i, "purple"));

        const aodvPath = Array.isArray(data.AODV.path) ? data.AODV.path : [];
        const coapPath = Array.isArray(data.CoAP.path) ? data.CoAP.path : [];

        for (let i = 0; i < aodvPath.length - 1; i++)
            drawEdge(aodvPath[i], aodvPath[i+1], "red");

        for (let i = 0; i < coapPath.length - 1; i++)
            drawEdge(coapPath[i], coapPath[i+1], "green");

        // ❌ DO NOT LOOP METRICS (this was your bug)
        document.getElementById("aodv_energy").innerText =
            data.AODV.metrics.energy_balance;

        document.getElementById("coap_energy").innerText =
            data.CoAP.metrics.energy_balance;
    });
}
