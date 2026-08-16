import subprocess, sys
keywords = [
    "corporate transfers melbourne",
    "melbourne corporate cars",
    "corporate chauffeur melbourne",
    "executive cars melbourne",
    "executive chauffeur melbourne",
    "executive airport transfers",
    "corporate limousine service",
    "corporate cars melbourne",
    "corporate limo service",
]
platforms = ["instagram", "facebook", "linkedin"]
for kw in keywords:
    for p in platforms:
        print("Generating:", kw, "/", p)
        subprocess.run([sys.executable, "cli.py", "generate", "--keywords", kw, "--platform", p])
print("ALL DONE")
