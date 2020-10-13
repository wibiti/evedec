'''
evedec.py
Reads and decrypts Eve Online python files and passes them to uncompyle2 to decompile.
  -Doesn't manipulate Eve process. Can be run with or without Eve running.
  -Searches for decryption key in the blue.dll file.
  -Requires uncompyle2 for actual decompilation.
  -Uses multiple processes to speed up decompilation.

Expects a evedec.ini file to specify Eve install location and output directory, e.g.:
[main]
eve_path = C:\Program Files (x86)\CCP\EVE\
store_path = ..\

'''

#function executed by each decompile process
def process_func(code_q, result_q, store_path, lock):
    okay_files = failed_files = 0
    try:
        import sys, os, marshal, errno, Queue
        import uncompyle2
        while 1:
            filename, marshalled_code = code_q.get(True, 5) #give up after 5 sec
            if filename == None: #None is our end marker
                break
            try:
                code = marshal.loads(marshalled_code[8:])
                
                #prepend our store_path
                filename = os.path.join(store_path, filename)
                filename = os.path.abspath(filename)
                try:
                    os.makedirs(os.path.dirname(filename))
                except OSError as e:
                    #the dir may already exist, in which case ignore error
                    if e.errno != errno.EEXIST:
                        raise
                try:
                    os.remove(filename+'_failed')
                    os.remove(filename+'c')
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise
                with open(filename, 'w') as out_file:
                    uncompyle2.uncompyle('2.7', code, out_file)
            except KeyboardInterrupt:
                raise
            except:
                with lock:
                    print '### Can\'t decompile %s' % filename
                    sys.stdout.flush()
                os.rename(filename, filename+'_failed')
                with open(filename+'c', 'wb') as codefile:
                    codefile.write(marshalled_code)
                failed_files += 1
            else:
                with lock:
                    print '+++ Okay decompiling %s' % filename
                    sys.stdout.flush()
                okay_files += 1
                
    except Queue.Empty: #timeout reached
        pass
    finally:
        result_q.put((okay_files, failed_files))

#executed once by the starting process
if __name__ == '__main__':
    #moved imports here so that the other processes don't import them unnecessarily
    import sys
    if sys.version[:3] != '2.7':
        print >>sys.stderr, '!!! Wrong Python version : %s.  Python 2.7 required.'
        sys.exit(-1)
    import os, cPickle, imp, zipfile, zlib, traceback
    from Queue import Empty
    from multiprocessing import Process, Queue, cpu_count, freeze_support, Lock
    from datetime import datetime
    from ConfigParser import ConfigParser

    freeze_support()
    
    startTime = datetime.now() #time this cpu hog
    
    #Get path to Eve installation from evedec.ini file
    config = ConfigParser()
    config.read('evedec.ini')
    eve_path = config.get('main', 'eve_path')
    
    #use version info from eve's common.ini to create directory name
    eveconfig = ConfigParser()
    eveconfig.read(os.path.join(eve_path, 'start.ini'))

    store_path = os.path.join(config.get('main', 'store_path'), \
      'eve-%s.%s' % (eveconfig.get('main', 'version'), eveconfig.get('main', 'build')))
    store_path = os.path.abspath(store_path)


    #queue of marshalled code objects
    code_queue = Queue()
    #queue of process results
    result_queue = Queue()
    
    sys.stdout.flush()
        
    try:
        #create decompile processes
        procs = []
        print_lock = Lock()
        for i in range(cpu_count()-1): #save one process for decompressing/decrypting
            procs.append(Process(target=process_func,
                                 args=(code_queue, result_queue, store_path, print_lock)));
            
        #start procs now; they will block on empty queue
        for p in procs:
            p.start()
            
        with zipfile.ZipFile(os.path.join(eve_path, 'code.ccp'), 'r') as zf:
            for filename in zf.namelist():
                if filename[-4:] == '.pyj':
                    code_queue.put( (filename[:-1], zlib.decompress(zf.read(filename))) )
                elif filename[-4:] == '.pyc':
                    code_queue.put( (filename[:-1], zf.read(filename)) )

        #this process is done except for waiting, so add one more decompile process
        p = Process(target=process_func,
                    args=(code_queue, result_queue, store_path, print_lock))
        p.start()
        procs.append(p)
        
        #add sentinel values to indicate end of queue
        for p in procs:
            code_queue.put( (None, None) )

        #wait for decompile processes to finish
        for p in procs:
            p.join() #join() will block until p is finished
        #pull results from the result queue
        okay_files = failed_files = 0
        try:
            while 1: #will terminate when queue.get() generates Empty exception
                (o, f) = result_queue.get(False)
                okay_files += o
                failed_files += f
        except Empty:
            pass
        print '# decompiled %i files: %i okay, %i failed' % \
              (okay_files + failed_files, okay_files, failed_files)
        print '# elapsed time:', datetime.now() - startTime
    except:
        traceback.print_exc()
        os._exit(0) #make Ctrl-C actually end process    
