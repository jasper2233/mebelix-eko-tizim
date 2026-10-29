"""MX Kroy SSO kalit jufti (EKO 3b, K6): RSA 2048.

Maxfiy kalit — MES muhitiga (`MX_SSO_PRIVATE_KEY`, bir qatorda `\n` bilan), ochiq kalit — MX muhitiga
(`MEBELIX_JWT_PUBLIC_KEY`). Maxfiy kalit faqat MES serverida qoladi.

    python -m app.commands.kroy_kalit
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    print("# MES (.env):")
    print("MX_SSO_PRIVATE_KEY=" + private.strip().replace("\n", "\\n"))
    print("\n# MX Kroy (.env):")
    print("MEBELIX_JWT_PUBLIC_KEY=" + public.strip().replace("\n", "\\n"))


if __name__ == "__main__":
    main()
