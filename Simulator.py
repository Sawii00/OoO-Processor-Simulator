import json



class Instruction:
    def __init__(self, pc, opcode, dest, first, second):
        self.pc = pc
        self.opcode = opcode
        self.dest = dest
        self.first = first
        self.second = second
        self.result = 0

    def __str__(self):
        return f"({self.pc}): {self.opcode} {self.dest}, {self.first}, {self.second};\n"

    def __repr__(self):
        return f"({self.pc}): {self.opcode} {self.dest}, {self.first}, {self.second};\n"


class ActiveListEntry:
    def __init__(self, pc, old_dest, logical_dest, done, exception):
        self.pc = pc
        self.old_dest = old_dest
        self.logical_dest = logical_dest
        self.done = done
        self.exception = exception


class IntegerQueueEntry:
    def __init__(self, dest_reg, a_rdy, a_tag, a_val, b_rdy, b_tag, b_val, opcode, pc):
        self.dest_reg = dest_reg
        self.a_rdy = a_rdy
        self.a_tag = a_tag
        self.a_val = a_val
        self.b_rdy = b_rdy
        self.b_tag = b_tag
        self.b_val = b_val
        self.opcode = opcode
        self.pc = pc


class ALU:
    def __init__(self):
        self.shift_reg = [None, None]

    def reset(self):
        self.shift_reg = [None, None]

    def push_instruction(self, instr: IntegerQueueEntry):
        assert self.shift_reg[0] is None
        self.shift_reg[0] = instr

    def tick(self):
        assert self.shift_reg[1] is None
        self.shift_reg[1] = self.shift_reg[0]
        self.shift_reg[0] = None

    def pop_result(self):
        if self.shift_reg[1] is not None:
            executed_instr = self.shift_reg[1]
            result = 0
            exception = 0
            if executed_instr.opcode in ["add", "addi"]:
                result = executed_instr.a_val + executed_instr.b_val
            elif executed_instr.opcode == "sub":
                result = executed_instr.a_val - executed_instr.b_val
            elif executed_instr.opcode == "mulu":
                result = executed_instr.a_val * executed_instr.b_val
            elif executed_instr.opcode == "divu":
                if executed_instr.b_val == 0:
                    exception = True
                else:
                    # NOTE: assignment mentions operands being __unsigned__
                    result = executed_instr.a_val / executed_instr.b_val
            elif executed_instr.opcode == "remu":
                if executed_instr.b_val == 0:
                    exception = True
                else:
                    # NOTE: assignment mentions operands being __unsigned__
                    result = executed_instr.a_val % executed_instr.b_val
            else:
                raise Exception("Invalid Instruction in Execution Stage")
            return result, exception, executed_instr
        else:
            return None


class CPU:
    def __init__(self, code):
        self.code = code
        self.pc = 0
        self.rf = [0 for i in range(64)]
        self.dir = []
        self.exception_flag = False
        self.e_pc = 0
        self.map_table = [i for i in range(32)]
        self.free_list = [i for i in range(32, 64)]
        self.busy_bit = [False for i in range(64)]
        self.active_list = []
        self.integer_queue = []

        self.state_log = []
        self.ALUs = [ALU(), ALU(), ALU(), ALU()]

    def reset(self):
        self.pc = 0
        self.rf = [0 for i in range(64)]
        self.dir = [0 for i in range(4)]
        self.exception_flag = False
        self.e_pc = 0
        self.map_table = [i for i in range(32)]
        self.free_list = [i for i in range(32, 64)]
        self.busy_bit = [False for i in range(64)]
        self.active_list = []
        self.integer_queue = []

        self.state_log = []
        self.ALUs = [ALU(), ALU(), ALU(), ALU()]

    def fetch_decode(self):
        if self.exception_flag:
            self.pc = 0x10000
            self.dir = []
            return
        for i in range(min(4 - len(self.dir), len(self.code) - self.pc)):
            self.dir.append(self.code[self.pc])
            self.pc += 1

    def rename_dispatch(self):
        pass

    def issue(self):
        issued = 0
        removed_ids = []
        for i, el in enumerate(self.integer_queue):
            if issued == 4:
                break
            if el.a_rdy and el.b_rdy:
                self.ALUs[issued].push_instruction(el)
                issued += 1
                removed_ids.append(i)
        removed_ids.sort(reverse=True)
        for id in removed_ids:
            self.integer_queue.pop(id)

    def exec1(self):
        for alu in self.ALUs:
            alu.tick()

    def exec2(self):
        for alu in self.ALUs:
            outcome = alu.pop_result()
            if outcome is not None:
                result, exception, instruction = outcome
                for el in self.active_list:
                    if el.pc == instruction.pc:
                        el.done = True
                        el.exception = exception
                        break
                # update integer_queue
                for el in self.integer_queue:
                    if el.a_tag == instruction.pc:
                        el.a_val = result
                        el.a_rdy = True
                    if el.b_tag == instruction.pc:
                        el.b_val = result
                        el.b_rdy = True
                # Physical Register Update
                self.busy_bit[instruction.dest_reg] = False
                self.rf[instruction.dest_reg] = result

    def commit(self):
        if not self.exception_flag:
            for i in range(4):
                if not self.active_list[i].done:
                    break
                if self.active_list[i].exception:
                    # Handle Exception
                    self.exception_flag = True
                    self.e_pc = self.active_list[i].pc
                    for alu in self.ALUs:
                        alu.reset()
                    self.integer_queue = []
                else:
                    el = self.active_list.pop(0)
                    self.free_list.append(el.old_dest)
        else:
            for i in range(min(4, len(self.active_list))):
                # Roll-back Active List
                last_instr = self.active_list.pop() # Grab last element
                curr_physical = self.map_table[last_instr.logical_dest]
                self.map_table[last_instr.logical_dest] = last_instr.old_dest
                self.free_list.append(curr_physical)
                self.busy_bit[curr_physical] = False # NOTE: do we need to do anything with last_instr.old_dest??

            if len(self.active_list) == 0:
                # Exception has been handled
                self.exception_flag = False
                # self.e_pc = 0

    def log_state(self):
        out = dict()
        out["PC"] = self.pc
        out["PhysicalRegisterFile"] = self.rf
        out["DecodedPCs"] = [el.pc for el in self.dir]
        out["ExceptionPC"] = self.e_pc
        out["Exception"] = self.exception_flag
        out["RegisterMapTable"] = self.map_table
        out["FreeList"] = self.free_list
        out["BusyBitTable"] = self.busy_bit
        out["ActiveList"] = [{"Done": el.done, "Exception": el.exception, "LogicalDestination": el.logical_dest,
                              "OldDestination": el.old_dest, "PC": el.pc} for el in self.active_list]
        out["IntegerQueue"] = [{"DestRegister": el.dest_reg, "OpAIsReady": el.a_rdy, "OpARegTag": el.a_tag,
                                "OpAValue": el.a_val, "OpBIsReady": el.b_rdy, "OpBRegTag": el.b_tag,
                                "OpBValue": el.b_val,
                                "OpCode": el.opcode, "PC": el.pc} for el in self.integer_queue]
        self.state_log.append(out)

    def dump(self, filename):
        with open(filename, "w") as file:
            json.dump(self.state_log, file)

    def check_asserts(self):
        assert len(self.active_list) <= 32
        assert len(self.integer_queue) <= 32
        assert len(self.dir) <= 4

    def start(self, filename=""):
        while self.pc < len(self.code) and not self.stop_sim:
            self.commit()
            self.exec2()
            self.exec1()
            self.issue()
            self.rename_dispatch()
            self.fetch_decode()
            self.check_asserts()
            self.log_state()

        if filename != "":
            self.dump(filename)
        else:
            print(self.state_log)


class Simulator:
    def __parse_input_file(self, filename):
        res = []
        with open(filename, "r") as file:
            code = json.load(file)
            for pc, instr in enumerate(code):
                opcode = instr.split(" ")[0].strip()
                rest = instr[instr.find(" "):]
                first_op = rest.split(",")[1].strip()
                second_op = rest.split(",")[2].strip()
                dest = rest.split(",")[0].strip()
                res.append(Instruction(pc, opcode, dest, first_op, second_op))
        return res

    def __init__(self, filename):
        self.code = self.__parse_input_file(filename)

    def run(self):
        cpu = CPU(self.code)
        cpu.start("out_log.json")
