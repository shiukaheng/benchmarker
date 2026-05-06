import hashlib



def calc_model_id(repo: str, digest: str) -> str:
    return hashlib.sha256(f"{repo}\0{digest}".encode("utf-8")).hexdigest()