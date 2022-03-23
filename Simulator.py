import json


class Instruction:
    def __init__(self, pc, opcode, dest, first, second):
        self.pc = pc
        self.opcode = opcode
        self.dest = dest
        self.first = first
        self.second = second

    def __str__(self):
        return f"({self.pc}): {self.opcode} {self.dest}, {self.first}, {self.second};\n"

    def __repr__(self):
        return f"({self.pc}): {self.opcode} {self.dest}, {self.first}, {self.second};\n"

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
        self.active_list =

    def reset(self):
        self.pc = 0

    def fetch_decode(self):
        pass

    def rename_dispatch(self):
        pass

    def issue(self):
        pass

    def exec1(self):
        pass

    def exec2(self):
        pass

    def commit(self):
        pass

    def dump(self, filename):
        pass

    def start(self, filename=""):
        while self.pc < len(self.code):
            self.commit()
            self.exec2()
            self.exec1()
            self.issue()
            self.rename_dispatch()
            self.fetch_decode()

            if filename != "":
                self.dump(filename)


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
        cpu.start()

