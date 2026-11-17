# devsecops-demo

โปรเจกต์ตัวอย่างสำหรับทดสอบ DevSecOps pipeline บน **GitHub + Jenkins**
มี 2 แอปเล็ก ๆ ที่ลูกค้าใช้บ่อย: **Node.js (Express)** และ **Python (Flask)**
แต่ละแอปมี Dockerfile และ Jenkinsfile ของตัวเอง

```
devsecops-demo/
├── node-app/            Express + lodash   (Jenkinsfile, Dockerfile, test/)
├── python-app/          Flask + requests   (Jenkinsfile, Dockerfile, tests/)
└── scripts/
    ├── setup-jenkins-host.sh   ติดตั้ง Docker บนเครื่อง Jenkins
    └── make-report.py          รวมผล scan เป็นหน้า HTML (reports/summary.html)
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

**แนะนำให้ commit `package-lock.json`** ด้วย (`cd node-app && npm install`) เพราะ `npm ci` ต้องใช้ไฟล์นี้
ถ้าไม่มี pipeline จะ fallback ไป `npm install` เอง แต่ผลจะไม่ reproducible

> การแก้ Jenkinsfile ผ่าน **Replay** มีผลแค่ build นั้น ต้องแก้ไฟล์ใน GitHub แล้ว push ด้วย ไม่งั้นรอบหน้าจะหาย

## 2) เตรียมเครื่อง Jenkins (Ubuntu ที่ติดตั้งด้วย apt)

```bash
bash scripts/setup-jenkins-host.sh
```

สคริปต์จะติดตั้ง Docker, เพิ่ม user `jenkins` เข้า group `docker`, restart Jenkins และ pull image ที่ใช้ล่วงหน้า
ตรวจว่าผ่านด้วย `sudo -u jenkins docker ps`

ทุก scanner รันด้วย `docker run` **ไม่ต้องติดตั้ง Jenkins plugin เพิ่ม** (ไม่ใช้ Docker Pipeline, SonarQube Scanner plugin)

### Credentials ที่ต้องสร้าง

สร้างที่ **Manage Jenkins → Credentials → System → Global credentials**
(ห้ามสร้างใน user credentials ของตัวเอง เพราะ job จะมองไม่เห็น)

| ID | ชนิด | ใช้เมื่อ | หมายเหตุ |
|---|---|---|---|
| `sonar-token` | Secret text | `RUN_SONAR` | token จาก SonarQube Cloud → My Account → Security |
| `registry-cred` | Username with password | `PUSH_IMAGE` | username = GitHub user, password = PAT (classic) ที่มีสิทธิ์ `write:packages` |

## 3) สร้าง Jenkins job (2 job)

| Job | Definition | Script Path |
|---|---|---|
| `demo-node-app` | Pipeline script from SCM (Git) | `node-app/Jenkinsfile` |
| `demo-python-app` | Pipeline script from SCM (Git) | `python-app/Jenkinsfile` |

- Repository URL: `https://github.com/<your-user>/devsecops-demo.git` (ถ้าเป็น private ให้เพิ่ม credentials แบบ username + token)
- Branch: `*/main`
- กด **Build Now** หนึ่งครั้งให้ Jenkins อ่าน parameters แล้วรอบถัดไปใช้ **Build with Parameters**

### Parameters หลัก

| Parameter | ความหมาย |
|---|---|
| `STRICT_MODE` | เปิด = เจอ finding แล้ว build FAILED (แดง) / ปิด = UNSTABLE (เหลือง) |
| `RUN_ZAP` | เปิด/ปิด DAST |
| `RUN_SONAR` | เปิดสแกน SonarQube Cloud |
| `SONAR_HOST_URL` | ค่าเริ่มต้น `https://sonarcloud.io` |
| `SONAR_ORG` | organization key บน SonarQube Cloud |
| `SONAR_PROJECT_KEY` | ต้องตรงกับ project key ที่แสดงบน SonarQube Cloud |
| `PUSH_IMAGE` | push image ขึ้น registry |
| `REGISTRY` | เช่น `ghcr.io/<github-user>` (**ตัวพิมพ์เล็กทั้งหมด**) |

### ตั้งค่า SonarQube Cloud (Free plan)

1. สร้างโปรเจกต์จาก GitHub repo และ **ปิด Automatic Analysis** (Administration → Analysis Method) ไม่งั้นสแกนจาก Jenkins จะชนกัน
2. แผน Free **ไม่มี webhook** จึงไม่ใช้ `waitForQualityGate` แต่ใช้ `-Dsonar.qualitygate.wait=true` ให้ scanner รอผลเอง (Quality Gate ไม่ผ่าน = exit code 3)
3. SonarQube ไม่ block pipeline เอง pipeline เป็นคนตัดสินว่า stage นี้ผ่านหรือไม่

## 4) Stage ที่มีใน pipeline

| Stage | Tool | License | ทำอะไร |
|---|---|---|---|
| Secret Scan | Gitleaks | open source | หา secret ในโค้ดและประวัติ commit |
| Install & Unit Test | npm test / pytest | open source | ติดตั้ง dependency และรัน test |
| SCA | npm audit / pip-audit | ฟรี | ตรวจ library ที่มีช่องโหว่ (CVE) |
| SAST | Semgrep (+ Bandit สำหรับ Python) | open source | สแกนซอร์สโค้ดหาโค้ดไม่ปลอดภัย |
| SAST (optional) | SonarQube Cloud (Free) | SaaS ฟรีสำหรับโปรเจกต์ที่ใช้ได้ตามแผน Free | รันด้วย `sonar-scanner-cli` ผ่าน Docker เปิดด้วย `RUN_SONAR` |
| Dockerfile Lint | Hadolint | open source | ตรวจ best practice ของ Dockerfile |
| Docker Build | Docker | open source | สร้าง image |
| Image Scan | Trivy | open source | สแกนช่องโหว่ใน image |
| SBOM | Syft | open source | ออกรายการ component (CycloneDX) |
| Smoke Test | curl | - | รัน container แล้วเรียก `/health` |
| DAST | OWASP ZAP baseline | open source | ยิงทดสอบแอปที่รันอยู่ (ใช้แทน Acunetix ตอน demo) |
| Push Image (optional) | docker push → **GHCR** | ฟรี | push ไป `ghcr.io/<user>/demo-node-app:<build>` เปิดด้วย `PUSH_IMAGE` ต้องมี `registry-cred` |
| Report (post) | `scripts/make-report.py` | - | รวมผลเป็น `reports/summary.html` |

## 5) รายงานผล

รายงานทั้งหมดอยู่ใน **Build Artifacts → reports/**

- **`summary.html`** — หน้าสรุปอ่านง่าย: จำนวน finding แยกตามความรุนแรง และตารางแยกตาม tool
- ไฟล์ดิบ (SARIF, JSON, HTML, SBOM) **ยังเก็บครบ** ในโฟลเดอร์เดียวกัน และ `summary.html` มีลิงก์ไปหาแต่ละไฟล์
- ผล SonarQube ดูที่ dashboard บน SonarQube Cloud (ใน `summary.html` มีลิงก์ให้)
- ถ้าสร้าง `summary.html` ไม่สำเร็จ build จะไม่ล้ม (stage report ข้ามไปเฉย ๆ)

> Jenkins มักตั้ง Content-Security-Policy เข้มกับ HTML ที่เก็บเป็น artifact
> ถ้าเปิดแล้วเห็นแต่ข้อความไม่มีสี ให้ดาวน์โหลดไปเปิดในเครื่อง

สร้างรายงานเองจากเครื่อง:

```bash
python scripts/make-report.py --reports reports --out reports/summary.html --app node-app --build 1
```

## 6) ผลที่คาดว่าจะเห็น (รอบแรกด้วยค่า default)

| Stage | ผล |
|---|---|
| Gitleaks | ผ่าน (ไม่มี secret จริง) |
| npm audit | เจอ lodash ระดับ High |
| pip-audit | เจอ requests ที่มี CVE |
| Semgrep / Bandit | **ขึ้นกับ rule set ที่ใช้** — ควรตรวจ `semgrep-*.sarif` ว่าเจอ `eval`, command injection, MD5 ใน insecure-demo หรือไม่ ถ้าไม่เจอให้เพิ่ม rule เช่น `p/security-audit` |
| SonarQube Cloud | Quality Gate อาจ **FAILED** ได้ตามปกติ (gate ตรวจ new code) |
| Trivy | เจอ lodash/requests และอาจมีช่องโหว่ของ base image |
| ZAP | มี warning เช่น security header ขาด, `X-Powered-By` |

Build จะเป็น **UNSTABLE (เหลือง)** ซึ่งเป็นผลที่ถูกต้อง ถ้าเปิด `STRICT_MODE` จะเป็น **FAILED (แดง)**

## 7) ลองเล่นต่อ

- อัปเดต `lodash` เป็น **4.18.1** (`^4.17.21` ยังไม่พอตามผล audit) หรือ `requests` เป็น `2.32.3` แล้ว push เพื่อดู SCA/Trivy สะอาดขึ้น
- ลบไฟล์ `insecure-demo.js` / `insecure_demo.py` เพื่อดู SAST สะอาดขึ้น
- ตั้ง GitHub webhook ให้ Jenkins build อัตโนมัติเมื่อ push
- เปลี่ยน `RUN_ZAP` เป็น false ถ้าอยากให้ build เร็วขึ้น
- เปิด `STRICT_MODE` เพื่อดูพฤติกรรม quality gate ที่ block pipeline

## Troubleshooting

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| `permission denied ... docker.sock` | user jenkins ยังไม่อยู่ใน group docker หรือยังไม่ restart Jenkins: `sudo usermod -aG docker jenkins && sudo systemctl restart jenkins` |
| `docker: command not found` (exit 127) | ยังไม่ได้ติดตั้ง Docker: รัน `scripts/setup-jenkins-host.sh` |
| `Invalid agent type "docker"` | ไม่มี Docker Pipeline plugin — Jenkinsfile นี้ใช้ `docker run` ใน `sh` แทน ตรวจว่าใช้ไฟล์ล่าสุดจาก GitHub |
| `npm ci` EUSAGE | ไม่มี `package-lock.json` — รัน `npm install` แล้ว commit lock file |
| Hadolint DL3025 | ใน `HEALTHCHECK` ให้ใช้ CMD แบบ JSON array |
| `No such DSL method 'withSonarQubeEnv'` | ไม่ต้องใช้ SonarQube plugin — Jenkinsfile นี้เรียก scanner ผ่าน Docker |
| Sonar: `Unable to create directory .../.sonar/cache` | ตั้ง `-e SONAR_USER_HOME=/tmp/.sonar` (ใน Jenkinsfile ตั้งไว้แล้ว) |
| Sonar: `Unable to create root temp directory .../.sonartmp` | ใส่ `-Dsonar.working.directory=/tmp/sonar-work` (ตั้งไว้แล้ว) |
| Sonar: พารามิเตอร์ว่าง/ไม่เจอโปรเจกต์ | ตรวจ `SONAR_ORG` และ `SONAR_PROJECT_KEY` ให้ตรงกับบน SonarQube Cloud และปิด Automatic Analysis |
| Push Image ล้มภายในไม่กี่ ms | Jenkins มองไม่เห็น credential `registry-cred` — สร้างใหม่ใน **System → Global** |
| Push ถูกปฏิเสธ (denied) | PAT ต้องมี `write:packages` และ `REGISTRY` ต้องเป็นตัวพิมพ์เล็ก เช่น `ghcr.io/<user>` |
| Image Scan (Trivy) เป็นสีแดง | เปิด `STRICT_MODE` อยู่ — ปิดเพื่อให้เป็น UNSTABLE |
| `summary.html` เปิดแล้วไม่มีสไตล์ | CSP ของ Jenkins บล็อก inline CSS — ดาวน์โหลดไปเปิดในเครื่อง |
| Semgrep / Trivy / pip-audit ดึงข้อมูลไม่ได้ | เครื่อง Jenkins ต้องออกอินเทอร์เน็ตได้ (rules, CVE database, PyPI) |
| ลบ workspace ไม่ได้ (permission) | มีไฟล์ของ root ตกค้าง: `sudo rm -rf /var/lib/jenkins/workspace/<job>*` |
