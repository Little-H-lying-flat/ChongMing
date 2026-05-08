const payload = {
    project_id: "proj_001",
    requirement_text: "Need a login page",
    target_type: "MIXED"
};

fetch("http://127.0.0.1:3000/api/v1/design/analyze/async", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
})
.then(async res => {
    console.log("Status:", res.status);
    console.log("StatusText:", res.statusText);
    const text = await res.text();
    console.log("Body:", text);
})
.catch(err => {
    console.error("Fetch error:", err);
});
