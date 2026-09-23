from backend.app.security.pii_detector import PIIDetector
detector = PIIDetector()
res = detector.scan("API_KEY=sk-proj-abcdefghij1234567890ABCDEFGHIJ1234567890")
print("API_KEY test:", res.findings)

res2 = detector.scan("Card number: 4532 1234 5678 9010")
print("VISA test:", res2.findings)

