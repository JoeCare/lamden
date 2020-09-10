from unittest import TestCase
from lamden.crypto import transaction
from lamden.crypto.transaction import build_transaction
from lamden.crypto.wallet import Wallet, verify
from contracting.db.encoder import encode, decode
from lamden import storage
from contracting.client import ContractingClient
import decimal
import json


class TestTransactionBuilder(TestCase):
    def test_init_valid_doesnt_assert(self):
        build_transaction(
            wallet=Wallet(),
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

    def test_init_invalid_format_raises_assert(self):
        with self.assertRaises(AssertionError):
            build_transaction(
                wallet=Wallet(),
                processor='b' * 65,
                stamps=123,
                nonce=0,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 123.0,
                    'to': 'jeff'
                }
            )

    def test_sign_works_properly(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        res = verify(
            w.verifying_key,
            encode(decoded['payload']),
            decoded['metadata']['signature']
        )

        self.assertTrue(res)

    def test_serialize_works_properly(self):
        w = Wallet()

        expected = {
                'sender': w.verifying_key,
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            }

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        self.assertDictEqual(decoded['payload'], expected)


class TestValidator(TestCase):
    def setUp(self):
        self.driver = storage.NonceStorage()
        self.driver.flush()

    def tearDown(self):
        self.driver.flush()

    def test_check_tx_formatting_succeeds(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': decimal.Decimal('123.872345873452873459873459870'),
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        error = transaction.check_tx_formatting(decoded, 'b' * 64)
        self.assertIsNone(error)

    def test_check_tx_formatting_not_formatted_fails(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)
        decoded['payload']['nonce'] = -123

        with self.assertRaises(transaction.TransactionFormattingError):
            transaction.check_tx_formatting(decoded, 'b' * 64)

    def test_check_tx_formatting_incorrect_processor_fails(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123.0,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        with self.assertRaises(transaction.TransactionProcessorInvalid):
            transaction.check_tx_formatting(decoded, 'c' * 64)

    def test_check_tx_formatting_signature_fails(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)
        decoded['payload']['sender'] = 'a' * 64

        with self.assertRaises(transaction.TransactionSignatureInvalid):
            transaction.check_tx_formatting(decoded, 'b' * 64)

    def test_get_nonces_when_none_exist_return_zeros(self):
        n, p = transaction.get_nonces('a' * 64, 'b' * 64, self.driver)
        self.assertEqual(n, 0)
        self.assertEqual(p, 0)

    def test_get_nonces_correct_when_exist(self):
        sender = 'a' * 32
        processor = 'b' * 32

        self.driver.set_pending_nonce(
            sender=sender,
            processor=processor,
            value=5
        )

        self.driver.set_nonce(
            sender=sender,
            processor=processor,
            value=3
        )

        n, p = transaction.get_nonces(
            sender=sender,
            processor=processor,
            driver=self.driver
        )
        self.assertEqual(n, 3)
        self.assertEqual(p, 5)

    def test_get_pending_nonce_if_strict_increments(self):
        new_pending_nonce = transaction.get_new_pending_nonce(
            tx_nonce=2,
            nonce=1,
            pending_nonce=2
        )

        self.assertEqual(new_pending_nonce, 3)

    def test_get_pending_nonce_if_not_strict_is_highest_nonce(self):
        new_pending_nonce = transaction.get_new_pending_nonce(
            tx_nonce=3,
            nonce=1,
            pending_nonce=2,
            strict=False
        )

        self.assertEqual(new_pending_nonce, 4)

    def test_get_pending_nonce_if_strict_invalid(self):
        with self.assertRaises(transaction.TransactionNonceInvalid):
            transaction.get_new_pending_nonce(
                tx_nonce=3,
                nonce=1,
                pending_nonce=2
            )

    def test_get_pending_nonce_if_not_strict_invalid(self):
        with self.assertRaises(transaction.TransactionNonceInvalid):
            transaction.get_new_pending_nonce(
                tx_nonce=1,
                nonce=1,
                pending_nonce=2,
                strict=False
            )

    def test_get_pending_nonce_too_many_tx_per_block_raise_error(self):
        with self.assertRaises(transaction.TransactionTooManyPendingException):
            transaction.get_new_pending_nonce(
                tx_nonce=16,
                nonce=0,
                pending_nonce=0
            )

    def test_get_pending_nonce_too_many_tx_per_block_raise_error_pending(self):
        with self.assertRaises(transaction.TransactionTooManyPendingException):
            transaction.get_new_pending_nonce(
                tx_nonce=17,
                nonce=0,
                pending_nonce=1
            )

    def test_has_enough_stamps_passes(self):
        transaction.has_enough_stamps(
            balance=10,
            stamps_per_tau=10000,
            stamps_supplied=1000,
        )

    def test_has_enough_stamps_fails(self):
        with self.assertRaises(transaction.TransactionSenderTooFewStamps):
            transaction.has_enough_stamps(
                balance=10,
                stamps_per_tau=10000,
                stamps_supplied=100001,
            )

    def test_has_enough_stamps_fails_minimum_stamps(self):
        with self.assertRaises(transaction.TransactionSenderTooFewStamps):
            transaction.has_enough_stamps(
                balance=10,
                stamps_per_tau=10000,
                stamps_supplied=100000,
                contract='currency',
                function='transfer',
                amount=10
            )

    def test_contract_is_valid_passes(self):
        transaction.contract_name_is_valid(
            contract='submission',
            function='submit_contract',
            name='con_hello'
        )

    def test_contract_fails(self):
        with self.assertRaises(transaction.TransactionContractNameInvalid):
            transaction.contract_name_is_valid(
                contract='submission',
                function='submit_contract',
                name='co_hello'
            )

    def test_transaction_is_not_expired_true_if_within_timeout(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        self.assertTrue(transaction.transaction_is_not_expired(decoded))

    def test_transaction_is_expired_false_if_outside_timeout(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)
        decoded['metadata']['timestamp'] -= 1000

        self.assertFalse(transaction.transaction_is_not_expired(decoded))

    def test_transaction_is_valid_complete_test_passes(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        client = ContractingClient()
        client.flush()

        client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=20_000
        )

        transaction.transaction_is_valid(
            transaction=decoded,
            expected_processor='b' * 64,
            client=client,
            nonces=self.driver
        )

    def test_transaction_valid_for_fixed(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': {'__fixed__': '123.123'},
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        client = ContractingClient()
        client.flush()

        client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=20_000
        )

        transaction.transaction_is_valid(
            transaction=decoded,
            expected_processor='b' * 64,
            client=client,
            nonces=self.driver
        )

    def test_transaction_valid_for_fixed_edges(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': {'__fixed__': '1.0'},
                'to': 'jeff'
            }
        )

        print(tx)

        decoded = decode(tx)

        client = ContractingClient()
        client.flush()

        client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=20_000
        )

        transaction.transaction_is_valid(
            transaction=decoded,
            expected_processor='b' * 64,
            client=client,
            nonces=self.driver
        )

    def test_extract_payload_works(self):
        tx = '{"metadata":{"signature":"27d52552e22aaa40ac91805fbe2af231610b6f97d3d51015e93d951f68a66abd161c6b25a2bfafddb71949360d79e4f19e614241dc028cac32ee6f6b5ba06203","timestamp":1599676652},"payload":{"contract":"con_token_swap","function":"disperse","kwargs":{"amount":{"__fixed__":"1.0"},"hash":"0xa619c18ba18cbcf8525475ebeccc64e414eb1a491a1b7aa2c19f6a7efe89e000","to":"testdude"},"nonce":0,"processor":"e65ae8c2167ec016557d232e4cfe4a3db69bc3384d86c5fead4d58c7b2d51a04","sender":"f16c130ceb7ed9bcebde301488cfd507717d5d511674bc269c39ad41fc15d780","stamps_supplied":100}}'
        expected = '{"contract":"con_token_swap","function":"disperse","kwargs":{"amount":{"__fixed__":"1.0"},"hash":"0xa619c18ba18cbcf8525475ebeccc64e414eb1a491a1b7aa2c19f6a7efe89e000","to":"testdude"},"nonce":0,"processor":"e65ae8c2167ec016557d232e4cfe4a3db69bc3384d86c5fead4d58c7b2d51a04","sender":"f16c130ceb7ed9bcebde301488cfd507717d5d511674bc269c39ad41fc15d780","stamps_supplied":100}'

        p = transaction.extract_payload(tx)
        self.assertEqual(expected, p)

    def test_verify_raw_tx(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': {'__fixed__': '1.0'},
                'to': 'jeff'
            }
        )

        self.assertTrue(transaction.verify_raw_tx(tx))

    def test_convert_contracting_objects_works(self):
        payload = {'amount': decimal.Decimal('123.123120000')}
        print(transaction.convert_contracting_objects(payload))
