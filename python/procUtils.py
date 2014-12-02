# -*- coding: UTF-8 -*-

import os, time, pdb, threading, multiprocessing as mp
from multiprocessing import managers
import multiprocessing.dummy as md
from loggers import *

strTASK_KILL_COMMAND = 'taskkill /IM %s'
POOL_LOGGER = 'WorkerPool'


def startThread(target, *args, **kwargs):
  thread = threading.Thread(target=target, args=args, kwargs=kwargs)
  thread.daemon = True
  thread.start()
  return thread 

def get_names(args):
	return [a.__name__ for a in args]

class AbstractWorker(object):

	def init_worker_base(self, BaseClass, task_queue, result_queue, proc_func, proc_args, proc_kwargs):
		proc_args_mod = [task_queue, result_queue, proc_func]
		proc_args_mod.extend(proc_args)
		self.timeout = None

		self.task_queue = task_queue
		self.result_queue = result_queue

#		logOut('%s initializing base class: %s, kwargs: %s'%(self.__class__.__name__, proc_args_mod, proc_kwargs))
		BaseClass.__init__(self, target=self.task_processor, args=proc_args_mod, kwargs=proc_kwargs)

	def __del__(self):
		logOut('Worker object deleting...', logger_name = POOL_LOGGER)

	def put_task(self, task):
		self.task_queue.put(task)

	def get_result(self):
		return self.result_queue.get()


class LowLevelWorkerMixin:

	def task_processor(self, task_queue, result_queue, proc_func, *proc_args, **proc_kwargs):
		return proc_func(task_queue, result_queue, *proc_args, **proc_kwargs)


class BaseWorkerMixin:

	def task_processor(self, task_queue, result_queue, proc_func, *proc_args, **proc_kwargs):
#	def run(self):
		logDbg('Starting worker...', logger_name = POOL_LOGGER)
		logOut('%d tasks in queue'%task_queue.qsize(), logger_name = POOL_LOGGER)
#		task_queue, result_queue, proc_func = self.run_args
		logOut('Getting task from queue...', logger_name = POOL_LOGGER)

		task = task_queue.get(timeout=self.timeout)
		while task!=None:
			logOut('Processing task %s...'%repr(task), logger_name = POOL_LOGGER)
#			res = proc_func(task, *self.proc_args, **self.proc_kwargs)

			try:
				res = proc_func(task, *proc_args, **proc_kwargs)
			except Exception as ex:
#				logExc('%s proc_func args: %s, kwargs: %s'%(self.__class__.__name__, get_names(proc_args), get_names(proc_kwargs)))
				logExc('%s proc_func'%(self.__class__.__name__))
				raise ex

#			logOut('Task done. Putting into result queue...', logger_name = POOL_LOGGER)
#			logOut('%d tasks left in queue'%task_queue.qsize())
			if isinstance(res, WorkerMultiResult):
				logOut('Putting WorkerMultiResult obj content -> RQ. RQ before insertion size: %d'%result_queue.qsize(), logger_name = POOL_LOGGER)
				map(result_queue.put, res)
				logOut('RQ after insertion size: %d'%result_queue.qsize(), logger_name = POOL_LOGGER)
			else:
				result_queue.put(res)

			logOut('Result queued', logger_name = POOL_LOGGER)
			task = task_queue.get(timeout=self.timeout)

		logOut('Worker %d finished'%self.pid, logger_name = POOL_LOGGER)


class AbstractWorkerProcess(mp.Process, AbstractWorker):

	def __init__(self, task_queue, result_queue, proc_func, *proc_args, **proc_kwargs):

		self.init_worker_base(mp.Process, task_queue, result_queue, proc_func, *proc_args, **proc_kwargs)
#		mp.Process.__init__(self, target=self.task_processor, args=proc_args, kwargs=proc_kwargs)
#		self.run_args = task_queue, result_queue, proc_func
#		self.proc_args = proc_args
#		self.proc_kwargs = proc_kwargs
#		mp.Process.__init__(self)


class LowLevelWorker(AbstractWorkerProcess, LowLevelWorkerMixin): pass
class WorkerProcess(AbstractWorkerProcess, BaseWorkerMixin): pass

class DummyWorker(md.Process, AbstractWorker, BaseWorkerMixin):#

	def __init__(self, task_queue, result_queue, proc_func, *proc_args, **proc_kwargs):
		self.pid = 0x3AEB1Cb
		self.init_worker_base(md.Process, task_queue, result_queue, proc_func, *proc_args, **proc_kwargs)
	
	def task_processor(self, proc_func, *proc_args, **proc_kwargs):
		superclass = super(self.__class__, self)
		res = superclass.task_processor(proc_func, *proc_args, **proc_kwargs)
		return res

	def terminate(self):
		self.alive = False


class SingleTaskWorker(WorkerProcess): pass


class WorkerMultiResult(list): pass

#	def __init__(self, task_queue):

#	def append(self, task_queue):

def create_proc_worker(WorkerClass, task_queue, result_queue, proc_func, *args, **kwargs):
#	worker = WorkerClass(target=proc_func, args=args, kwargs=kwargs)
	#worker.daemon = True
#	worker.start()
	return WorkerClass(task_queue, result_queue, proc_func, args, kwargs)

		

def createProcessPool(worker_count, task_queue, result_queue, WP_Class, proc_func, *args, **kwargs):
	logOut('Creating pool of %d workers...'%worker_count, logger_name = POOL_LOGGER)
	worker_list = []
	for i in range(worker_count):
		worker = create_proc_worker(WP_Class, task_queue, result_queue, proc_func, *args, **kwargs)
		worker_list.append(worker)
	
	#logOut('db created')
	return worker_list


class ProcessPool:

	def __init__(self, worker_count, immediate_start, proc_func, MP_WorkerClass=WorkerProcess, mp_only=False, *proc_args, **proc_kwargs):
		worker_class, queue_class = (MP_WorkerClass, mp.Queue) if 1<worker_count or mp_only else (DummyWorker, md.Queue)
		self.configure(worker_class, queue_class, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs)

	def configure(self, WP_Class, QueueClass, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs):
		self.task_queue = QueueClass()
		self.result_queue = QueueClass()
		self.worker_list = createProcessPool(worker_count, self.task_queue, self.result_queue, WP_Class, proc_func, *proc_args, **proc_kwargs)

		self.started = False
		if immediate_start:
			self.start()


	def __del__(self):
		for worker in self.worker_list:
			if not worker:
				continue

			worker.terminate()
			del worker

	def start(self):
		if self.started:
			return

		logOut('Starting pool...', logger_name = POOL_LOGGER)
#		logOut('%d tasks in queue'%self.task_queue.qsize())
		for worker in self.worker_list:
			worker.start()

		self.started = True


	def put_task(self, task):
		self.task_queue.put(task)


	def put_task_terminators(self):
		for i in range(len(self.worker_list)):
			self.put_task(None)


	def put_task_list(self, task_list, fPutTerminators=True):
		for task in task_list:
			self.task_queue.put(task)

		logOut('put_task_list. Task queue new size: %d'%self.task_queue.qsize(), logger_name = POOL_LOGGER)
		if fPutTerminators:
			self.put_task_terminators()


	def join(self):
		while not self.hasFinishedProcessing():
			time.sleep(0.001)


	def join_old(self):
		worker_list_len = len(self.worker_list)
		for i, worker in enumerate(self.worker_list):
			logOut('Waiting for worker %d/%d finish'%(i+1, worker_list_len), logger_name = POOL_LOGGER)
			worker.join()
	
		logOut('All workers joined', logger_name = POOL_LOGGER)

	def hasFinishedProcessing(self):
		return all(not w.is_alive() for w in self.worker_list)


	def wait_for_new_results(self):
		while not self.result_queue.qsize():
			time.sleep(0.1)


	def get_results(self):
		self.join()
		return self.get_results_nowait()


	def get_results_nowait(self):
		result = []
		while True:
			try:
#				logDbg('Getting pool results from queue', logger_name = POOL_LOGGER)
#				res = self.result_queue.get(timeout=1)
#				logDbg('Got %d pool results'%res, logger_name = POOL_LOGGER)
				res = self.result_queue.get_nowait()
			except:
				break

			result.append(res)
		
		logOut('Got %d pool results. %d tasks left in queue'%(len(result), self.task_queue.qsize()), logger_name = POOL_LOGGER)
		return result


class AddressPoolTask(object):
	def __init__(worker_id, task):
		self.worker_id = worker_id
		self.task = task

class AddressedProcessingPool(ProcessPool):

#	def __init__(self, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs):
#		worker_class, queue_class = (WorkerProcess, mp.Queue) if 1<worker_count else (DummyWorker, md.Queue)
#		self.configure(worker_class, queue_class, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs)

	def configure(self, WP_Class, QueueClass, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs):
#		import uuid

#		self.task_queue = QueueClass()
		self.result_queue = QueueClass()

		self.worker_map = {}
		self.workers_task_queues = {}

#		createProcessPool(worker_count, self.task_queue, self.result_queue, WP_Class, proc_func, *proc_args, **proc_kwargs)
		logOut('Creating pool of %d workers...'%worker_count, logger_name = POOL_LOGGER)
		
		for i in range(worker_count):
#			id = uuid.UUID().int
			self.worker_map[i] = create_proc_worker(WP_Class, QueueClass(), QueueClass(), proc_func, *proc_args, **proc_kwargs)

		self.worker_list = self.worker_map.values()


		self.started = False
		if immediate_start:
			self.start()


	def put_task(self, worker_id, task):
		self.worker_map[worker_id].put_task(task)


class SingleTaskProcessPool(ProcessPool):

	def __init__(self, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs):
		self.configure(SingleTaskWorker, worker_count, immediate_start, proc_func, *proc_args, **proc_kwargs)



class PoolProcessingPipe(ProcessPool):

	def get_results(self):
		result = []
		while not (self.result_queue.empty() and self.hasFinishedProcessing()):
			try:
				res = self.result_queue.get(timeout=0.01)
			except:
				continue

			result.append(res)
		
		return result


def processPool(WorkerClass, worker_count, proc_func, *args, **kwargs):
	pool = ProcessPool(worker_count, proc_func, *args, **kwargs)

	#logOut('db created')
#	pool.join()
	return pool



def thPoolProcess(worker_count, proc_func, *args, **kwargs):
	p = processPool(md.Process, worker_count, True, proc_func, *args, **kwargs)
	p.join()
	
def psPoolProcess(worker_count, proc_func, *args, **kwargs):
	p = processPool(mp.Process, worker_count, True, proc_func, *args, **kwargs)
	p.join()


def functionThreader(f):
  def wrapper(*args, **kwargs):
    return startThread(f, *args, **kwargs)
  
  return wrapper


@functionThreader
def start_worker_process(f, *proc_args, **proc_kwargs):
	mgr = managers.SyncManager()
	mgr.start()
	shared_list = mgr.list()

	proc_args = list(proc_args)
	res_list = proc_args[0]
	proc_args[0] = shared_list
#	pdb.set_trace()
	proc = mp.Process(target=f, args=proc_args, kwargs=proc_kwargs)
	proc.start()
	proc.join()
	res_list.extend(shared_list)
  
#	logOutLen('shared_list', shared_list)
#	pdb.set_trace()
#	return proc



def functionProcessWrap(f, *args, **kwargs):
#	pdb.set_trace()
	proc = mp.Process(target=f, args=args, kwargs=kwargs)
	proc.start()
	return proc


def functionProcessWrapper(f):

	def wrapper(*proc_args, **proc_kwargs):
		return functionProcessWrap(f, *proc_args, **proc_kwargs)
  
#	pdb.set_trace()
	return wrapper


#@functionThreader
def functionProcessWrapResult(f):
	mgr = managers.SyncManager()
	mgr.start()
	shared_list = mgr.list()

#	@functionThreader
	def wrapper(*proc_args, **proc_kwargs):
		proc_args = list(proc_args)
		res_list = proc_args[0]
		proc_args[0] = shared_list
#	pdb.set_trace()
		proc = mp.Process(target=f, args=proc_args, kwargs=proc_kwargs)
		proc.start()
		proc.join()
		res_list.extend(shared_list)
#		return proc
  
	logOutLen('shared_list', shared_list)
#	pdb.set_trace()
	return wrapper

def threadFunctionLocker(f):
  thread_lock = threading.Lock()
  def wrapper(*args, **kwargs):
    thread_lock.acquire()
    res = f(*args, **kwargs)
    thread_lock.release()
    return res

  return wrapper
      

#def killProcess(astrProgramImage):
#  PID_list = EnumProcesses()
#  hProcess = win32process.OpenProcess(DELETE, True, pid)
#  win32process.TerminateProcess(hProcess)

def taskKill(astrProgramImage):
  os.system(strTASK_KILL_COMMAND%astrProgramImage)
