from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packages.phase1_trust import TrustKey,QualificationTrustStore

def test_trust_store_rotation_policy():
 old=Ed25519PrivateKey.generate(); new=Ed25519PrivateKey.generate(); revoked=Ed25519PrivateKey.generate(); msg=b'phase1'
 ok=old.public_key().public_bytes_raw(); nk=new.public_key().public_bytes_raw(); rk=revoked.public_key().public_bytes_raw()
 oid=QualificationTrustStore.key_id(ok); nid=QualificationTrustStore.key_id(nk); rid=QualificationTrustStore.key_id(rk)
 store=QualificationTrustStore([TrustKey(oid,ok,'RETIRED'),TrustKey(nid,nk,'ACTIVE'),TrustKey(rid,rk,'REVOKED')])
 assert store.verify(oid,msg,old.sign(msg)); assert not store.can_issue(oid)
 assert store.verify(nid,msg,new.sign(msg)); assert store.can_issue(nid)
 assert not store.verify(rid,msg,revoked.sign(msg)); assert not store.can_issue(rid)

def test_unknown_key_is_rejected():
 k=Ed25519PrivateKey.generate(); store=QualificationTrustStore([]); assert not store.verify('unknown',b'x',k.sign(b'x'))
