import time
import inspect

from artiq.experiment import *

import remote_exec_processing


class RemoteExecDemo(EnvExperiment):
    def build(self):
        self.setattr_device("camera_sim")
        self.setattr_device("scheduler")
        self.setattr_argument("remote_exec", BooleanValue(False))
        self.setattr_argument("show_picture", BooleanValue(True), "Local options")
        self.setattr_argument("enable_fit", BooleanValue(True), "Local options")
        if self.remote_exec:
            self.setattr_device("camera_sim_rexec")

    def prepare(self):
        if self.remote_exec:
            self.camera_sim_rexec.add_code(
                inspect.getsource(remote_exec_processing))

    def set_dataset(self, name, *args, **kwargs):
        EnvExperiment.set_dataset(self, "rexec_demo." + name,
                                  *args, **kwargs)

    def transfer_parameters(self, parameters):
        w, h, cx, cy = parameters
        self.set_dataset("gaussian_w", w, save=False, broadcast=True)
        self.set_dataset("gaussian_h", h, save=False, broadcast=True)
        self.set_dataset("gaussian_cx", cx, save=False, broadcast=True)
        self.set_dataset("gaussian_cy", cy, save=False, broadcast=True)

    def fps_meter(self):
        t = time.monotonic()
        if hasattr(self, "last_pt_update"):
            self.iter_count += 1
            dt = t - self.last_pt_update
            if dt >= 5:
                pt = dt/self.iter_count
                self.set_dataset("picture_pt", pt, save=False, broadcast=True)
                self.last_pt_update = t
                self.iter_count = 0
        else:
            self.last_pt_update = t
            self.iter_count = 0

    def run_local(self):
        while True:
            self.fps_meter()
            data = self.camera_sim.get_picture()
            if self.show_picture:
                self.set_dataset("picture", data, save=False, broadcast=True)
            if self.enable_fit:
                self.transfer_parameters(remote_exec_processing.fit(data))
            self.scheduler.pause()

    def run_remote(self):
        while True:
            self.fps_meter()
            self.transfer_parameters(self.camera_sim_rexec.call("get_and_fit"))
            self.scheduler.pause()

    def run(self):
        try:
            if self.remote_exec:
                self.run_remote()
            else:
                self.run_local()
        except TerminationRequested:
            pass
