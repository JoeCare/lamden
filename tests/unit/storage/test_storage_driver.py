import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.utils.hasher import Hasher


TEST_IP = '127.0.0.1'
MN_SK = TESTNET_MASTERNODES[0]['sk']
MN_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']


class TestStorageDriver(TestCase):

    @classmethod
    def setUpClass(cls):
        MasterOps.init_master(key = MN_SK)
        cls.driver = StorageDriver()

    def setUp(self):
        MDB.reset_db()

    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    def test_store_block(self):
        sub_blocks = [SubBlockBuilder.create(idx=i) for i in range(2)]
        block = self.driver.store_block(sub_blocks)
        last_stored_hash = self.driver.get_latest_block_hash()

        tx = sub_blocks[0].transactions[0].transaction
        tx_hash = Hasher.hash(tx)

        self.assertEqual(block.block_num, 1)
        self.assertEqual(block.block_hash, last_stored_hash)

    # @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    # def test_get_latest_blocks(self):
    #     blocks = []
    #     for i in range(5):
    #         if len(blocks) > 0:
    #             block = BlockDataBuilder.create_block(prev_block_hash=blocks[-1].block_hash, blk_num=len(blocks)+1)
    #         else:
    #             block = BlockDataBuilder.create_block()
    #         blocks.append(block)
    #         self.driver.store_block(block, validate=False)
    #     latest_blocks = self.driver.get_latest_blocks(blocks[1].block_hash)
    #     self.assertEqual(len(latest_blocks), 3)
    #     self.assertEqual(latest_blocks[0].block_hash, blocks[2].block_hash)
    #     self.assertEqual(latest_blocks[1].block_hash, blocks[3].block_hash)
    #     self.assertEqual(latest_blocks[2].block_hash, blocks[4].block_hash)


if __name__ == '__main__':
    unittest.main()
