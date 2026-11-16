# devsecops-demo

โปรเจกต์ตัวอย่างสำหรับทดสอบ DevSecOps pipeline บน **GitHub + Jenkins**
มี 2 แอปเล็ก ๆ ที่ลูกค้าใช้บ่อย: **Node.js (Express)** และ **Python (Flask)**
แต่ละแอปมี Dockerfile และ Jenkinsfile ของตัวเอง

```
devsecops-demo/
├── node-app/            Express + lodash   (Jenkinsfile, Dockerfile, test/)
├── python-app/          Flask + requests   (Jenkinsfile, Dockerfile, tests/)
└── scripts/setup-jenkins-host.sh
```

> **ตั้งใจใส่ช่องโหว่ไว้ให้ scanner เจอ** (เพื่อให้เห็นผลสแกนจริง)
> - `lodash 4.17.15` (Node) และ `requests 2.25.1` (Python) เป็นเวอร์ชันเก่าที่มี CVE
> - `node-app/src/insecure-demo.js` และ `python-app/app/insecure_demo.py` เขียนโค้ดไม่ปลอดภัยไว้ (ไม่ได้ถูกใช้โดยแอป)
> - ใช้เพื่อ demo เท่านั้น ห้ามนำไปใช้จริง

## 1) เอาขึ้น GitHub

```bash
cd devsecops-demo
git init -b main
git add .
git commit -m "Initial demo project"
git remote add origin https://github.com/<your-user>/devsecops-demo.git
git push -u origin main
```

(ถ้าอยากให้ `npm ci` ทำงานตรง ๆ ให้รัน `cd node-app && npm install` แล้ว commit `package-lock.json` ด้วย
ถ้าไม่ทำ pipeline จะ fallback ไป `npm install` เอง)

## 2) เตรียมเครื่อง Jenkins (Ubuntu ที่ติดตั้งด้วย apt)

```bash
bash scripts/setup-jenkins-host.sh
```

สคริปต์จะติดตั้ง Docker, เพิ่ม user `jenkins` เข้า group `docker`, restart Jenkins และ pull image ที่ใช้ล่วงหน้า
ตรวจว่าผ่านด้วย `sudo -u jenkins docker ps`

## 3) สร้าง Jenkins job (2 job)

| Job | Definition | Script Path |
|---|---|---|
| `demo-node-app` | Pipeline script from SCM (Git) | `node-app/Jenkinsfile` |
| `demo-python-app` | Pipeline script from SCM (Git) | `python-app/Jenkinsfile` |

- Repository URL: `https://github.com/<your-user>/devsecops-demo.git` (ถ้าเป็น private ให้เพิ่ม credentials แบบ username + token)
- Branch: `*/main`
- กด **Build Now** หนึ่งครั้งให้ Jenkins อ่าน parameters แล้วรอบถัดไปใช้ **Build with Parameters**

## 4) Stage ที่มีใน pipeline

| Stage | Tool | License | ทำอะไร |
|---|---|---|---|
| Secret Scan | Gitleaks | open source | หา secret ในโค้ดและประวัติ commit |
| Install & Unit Test | npm test / pytest | open source | ติดตั้ง dependency และรัน test |
| SCA | npm audit / pip-audit | ฟรี | ตรวจ library ที่มีช่องโหว่ (CVE) |
| SAST | Semgrep (+ Bandit สำหรับ Python) | open source | สแกนซอร์สโค้ดหาโค้ดไม่ปลอดภัย |
| SAST (optional) | SonarQube | Community ฟรี / Developer ขึ้นไปเสียเงิน | เปิดด้วย `RUN_SONAR` |
| Dockerfile Lint | Hadolint | open source | ตรวจ best practice ของ Dockerfile |
| Docker Build | Docker | open source | สร้าง image |
| Image Scan | Trivy | open source | สแกนช่องโหว่ใน image |
| SBOM | Syft | open source | ออกรายการ component (CycloneDX) |
| Smoke Test | curl | - | รัน container แล้วเรียก `/health` |
| DAST | OWASP ZAP baseline | open source | ยิงทดสอบแอปที่รันอยู่ (ใช้แทน Acunetix ตอน demo) |
| Push Image (optional) | docker push | - | เปิดด้วย `PUSH_IMAGE` |

รายงานทั้งหมดอยู่ใน **Build Artifacts → reports/** (SARIF, JSON, HTML, SBOM)

## 5) ผลที่คาดว่าจะเห็น (รอบแรกด้วยค่า default)

| Stage | ผล |
|---|---|
| Gitleaks | ผ่าน (ไม่มี secret จริง) |
| npm audit | เจอ lodash ระดับ High |
| pip-audit | เจอ requests ที่มี CVE |
| Semgrep / Bandit | เจอ `eval`, command injection, MD5 ใน insecure-demo |
| Trivy | เจอ lodash/requests และอาจมีช่องโหว่ของ base image |
| ZAP | มี warning เช่น security header ขาด, `X-Powered-By` |

Build จะเป็น **UNSTABLE (เหลือง)** ซึ่งเป็นผลที่ถูกต้อง ถ้าเปิด `STRICT_MODE` จะเป็น **FAILED (แดง)**

## 6) ลองเล่นต่อ

- แก้ `lodash` เป็น `^4.17.21` หรือ `requests` เป็น `2.32.3` แล้ว push เพื่อดู SCA/Trivy สะอาดขึ้น
- ลบไฟล์ `insecure-demo.js` / `insecure_demo.py` เพื่อดู SAST สะอาดขึ้น
- ตั้ง GitHub webhook ให้ Jenkins build อัตโนมัติเมื่อ push
- เปลี่ยน `RUN_ZAP` เป็น false ถ้าอยากให้ build เร็วขึ้น

## Troubleshooting

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| `permission denied ... docker.sock` | user jenkins ยังไม่อยู่ใน group docker หรือยังไม่ restart Jenkins: `sudo usermod -aG docker jenkins && sudo systemctl restart jenkins` |
| `docker: command not found` | ยังไม่ได้ติดตั้ง Docker: รัน `scripts/setup-jenkins-host.sh` |
| Semgrep / Trivy / pip-audit ดึงข้อมูลไม่ได้ | เครื่อง Jenkins ต้องออกอินเทอร์เน็ตได้ (rules, CVE database, PyPI) |
| ลบ workspace ไม่ได้ (permission) | มีไฟล์ของ root ตกค้าง: `sudo rm -rf /var/lib/jenkins/workspace/<job>*` |
| Quality Gate ค้าง | ยังไม่ได้ตั้ง webhook จาก SonarQube กลับมาที่ `<jenkins>/sonarqube-webhook/` |
