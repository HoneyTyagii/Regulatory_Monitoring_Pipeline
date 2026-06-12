from regmon.dedup import DeduplicationEngine, SqlFingerprintIndex
from regmon.db import create_database

base = "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective April 2024."
exact = "  THE reserve   bank of india HEREBY directs all scheduled commercial banks to comply with the revised kyc norms effective april 2024.  "
punct = "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective April 2024!!!"
near = "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective from April 2024 onwards."
diff = "The Securities and Exchange Board issued a circular about mutual fund disclosure requirements for asset management companies."

eng = DeduplicationEngine()
print("doc-1:", eng.check_and_add("doc-1", base).kind.value)
r2 = eng.check_and_add("doc-2", exact)
print("exact variant:", r2.kind.value, r2.matched_doc_id)
r3 = eng.check_and_add("doc-3", punct)
print("punctuation variant:", r3.kind.value, r3.matched_doc_id, round(r3.similarity, 3))
r4 = eng.check_and_add("doc-4", near)
print("minor edit:", r4.kind.value, r4.matched_doc_id, round(r4.similarity, 3))
r5 = eng.check_and_add("doc-5", diff)
print("different:", r5.kind.value)
print("uniques stored:", len(eng._index))

db = create_database("sqlite:///:memory:"); db.create_all()
DeduplicationEngine(SqlFingerprintIndex(db)).check_and_add("d1", base)
res = DeduplicationEngine(SqlFingerprintIndex(db)).check("d2" and near)
print("cross-run near:", res.kind.value, res.matched_doc_id)
db.dispose()
print("OK")
