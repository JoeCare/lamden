from cilantro.networking import Witness2

if __name__ == '__main__':
    # loop = asyncio.get_event_loop()  # add uvloop here
    w = Witness2(sub_port='8888', pub_port='8080')
    # loop.run_until_complete(w.start_subscribing())
    w.start_async()


