
from app import create_app,db
from app.models import AIGeneratorConfig
import os

app = create_app()

with app.app_context():
    print(f"Encryption Key Configured: {bool(app.config.get('ENCRYPTION_KEY'))}")
    
    # Create or get config
    config = AIGeneratorConfig.query.first()
    if not config:
        config = AIGeneratorConfig()
        db.session.add(config)
    
    # Test Setter (Encryption)
    test_key = "sk-test-12345-plaintext-key"
    print(f"Setting API Key: {test_key}")
    config.api_key = test_key
    db.session.commit()
    
    # Test Getter (Decryption)
    # Refresh from DB to ensure we are reading from storage
    db.session.expire(config)
    print(f"Retrieved API Key: {config.api_key}")
    
    # Verify internal storage is actually encrypted (should not match plaintext)
    # Access the raw column directly if possible, or check via weakref
    # In SQLAlchemy models, accessing the private attribute directly might work
    raw_value = config._api_key
    print(f"Raw Stored Value (Encrypted): {raw_value}")
    
    if config.api_key == test_key and raw_value != test_key and raw_value.startswith("gAAAA"):
        print("\n[SUCCESS] API Key is encrypted in DB and decrypted on access!")
    else:
        print("\n[FAILED] Encryption verification failed.")
        print(f"Decrypted match: {config.api_key == test_key}")
        print(f"Raw match (should be False): {raw_value == test_key}")
