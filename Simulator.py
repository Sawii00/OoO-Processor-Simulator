import json


class Instruction:
    """ Struct that contains decoded instruction fields."""

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


class ActiveListEntry:
    """ Struct that contains the fields of each entry within the Active List.

        old_dest: stores the old physical destination found in the mapping table for its logical destination
                    and is used to restore the CPU state upon roll-back
        logical_dest: logical register defined in the instruction

    """

    def __init__(self, pc, old_dest, logical_dest, done, exception):
        self.pc = pc
        self.old_dest = old_dest
        self.logical_dest = logical_dest
        self.done = done
        self.exception = exception


class IntegerQueueEntry:
    """ Struct that contains the fields of each entry within the Integer Queue."""

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
    """ Class definition of an ALU module that handles instruction execution in two cycles.

        In order to force the execution to take two cycles, a 2-element shift register is used to simulate two stages.
    """

    def __init__(self):
        self.shift_reg = [None, None]

    def reset(self):
        self.shift_reg = [None, None]

    def push_instruction(self, instr: IntegerQueueEntry):
        """The IntegerQueueEntry is pushed in the first slot of the shift register after making sure it is empty. """

        assert self.shift_reg[0] is None
        self.shift_reg[0] = instr

    def tick(self):
        """Shifts the element present in the first stage to the second slot to simulate transition to second stage."""

        assert self.shift_reg[1] is None
        self.shift_reg[1] = self.shift_reg[0]
        self.shift_reg[0] = None

    def pop_result(self):
        """If there is an instruction in the second stage, it is executed according to the opcode.

            Result, instruction, and whether an exception was caused are returned.
        """

        if self.shift_reg[1] is not None:
            executed_instr = self.shift_reg[1]
            self.shift_reg[1] = None
            result = 0
            exception = False
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
                    result = executed_instr.a_val // executed_instr.b_val
            elif executed_instr.opcode == "remu":
                if executed_instr.b_val == 0:
                    exception = True
                else:
                    result = executed_instr.a_val % executed_instr.b_val
            else:
                raise Exception(f"Invalid Instruction in Execution Stage: {executed_instr.opcode}")
            return result, exception, executed_instr
        else:
            return None


class CPU:
    """Main class defining the CPU pipeline and all of its stages.

        To simulate the pipeline execution, a backward stage pass is employed to update the states for each cycle. By
        iterating from the last to the first stage in sequence, we do not need to store any intermediate result and no
        race conditions should arise.
    """

    def extract_number(self, str):
        if not str[0].isdigit():
            return int(str[1:])
        else:
            return int(str)

    def __init__(self):
        self.code = []
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

        self.state_log = []  # List of dictionaries that stores CPU state for each cycle.
        self.ALUs = [ALU(), ALU(), ALU(), ALU()]

        self.stop = False 
        self.committed_instructions = 0

    def reset(self):
        self.code = []
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

        self.state_log = []  # List of dictionaries that stores CPU state for each cycle.
        self.ALUs = [ALU(), ALU(), ALU(), ALU()]

        self.stop = False 
        self.committed_instructions = 0
        
    def fetch_decode(self):
        """Executes the Fetch and Decode stage.

            If we are in exception mode, we set the PC to the exception handler address 0x10000 and empty the DIR, with
            no instructions being fetched.
            Otherwise, we fetch 4 instructions at a time until the program has been executed correctly.

            NOTE: the backpressure mechanism is implicit since the F&D can only fill empty slots within the DIR. If the
            Rename and Dispatch stage does not dispatch any instruction, the DIR will be kept full (since the
            specification asks us to only dispatch atomically in groups of 4 instructions) and thus no new instruction
            will be fetched by this stage.
            Despite iterating over the number of empty spots in the DIR, given the previous definition, it will either
            fetch 4 instructions or 0 since the only case in which the DIR can contain < 4 instructions is if the code
            has been completely fetched and there were not 4 instructions available to be fetched.
        """

        if self.exception_flag:
            self.pc = 0x10000
            self.dir = []
            return
        for i in range(min(4 - len(self.dir), len(self.code) - self.pc)):
            self.dir.append(self.code[self.pc])
            self.pc += 1

    # Forwarding path handled by execute phase
    def rename_dispatch(self):
        """ Executes the Rename and Dispatch stage.

            If we are in exception mode, we return and stall the stage by not dispatching anything.
            Otherwise we check that we are able to correctly rename and dispatch ALL 4 instructions by making sure there
            are at least 4 slots available within ActiveList, IntegerQueue, and that there are at least 4 free physical
            registers available. If that is not the case we stall and dispatch NO instruction.

            If we can dispatch all 4, we start by extracting the required fields and building the ActiveListEntry and
            IntegerQueueEntry structs with the correct parameters.
        """

        if self.exception_flag:
            return
        if (len(self.dir) > 32 - len(self.active_list)) or (len(self.dir) > 32 - len(self.integer_queue)) or (
                len(self.dir) > len(self.free_list)):
            return
        curr_dir_length = len(self.dir)
        for i in range(curr_dir_length):
            instruction = self.dir.pop(0)
            physical_reg = self.free_list.pop(0)
            old_physical_dest = self.map_table[self.extract_number(instruction.dest)]
            first_op = self.extract_number(instruction.first)
            a_rdy = not self.busy_bit[self.map_table[first_op]]
            a_tag = self.map_table[first_op] 
            a_val = self.rf[self.map_table[first_op]] # Even if not ready, we don't care about it 
            second_op = self.extract_number(instruction.second)
            is_immediate = instruction.second[0].isdigit()  # We check if the second operand is a register or immediate
            b_rdy = not self.busy_bit[self.map_table[second_op]] if not is_immediate else True
            b_tag = self.map_table[second_op]
            b_val = self.rf[self.map_table[second_op]] if not is_immediate else second_op # Even if not ready, we don't care about it
            self.map_table[self.extract_number(instruction.dest)] = physical_reg  # Mapping logical to physical register
            self.busy_bit[physical_reg] = True  # Setting the physical destination as busy
            self.integer_queue.append(
                IntegerQueueEntry(physical_reg, a_rdy, a_tag, a_val, b_rdy, b_tag, b_val, instruction.opcode,
                                  instruction.pc))
            self.active_list.append(
                ActiveListEntry(instruction.pc, old_physical_dest, self.extract_number(instruction.dest), False, False))

    def issue(self):
        """Executes the Issue Stage.

            This stage tries to issue up to 4 "ready instructions" that have all operands ready. They are pushed to any
            of the 4 ALUs (which are functionally identical) and the entries are removed from the IntegerQueue.

            NOTE: we do not need explicit stall upon exception, because the commit stage in exception mode empties the
            integer queue, and thus the issue stage will not iterate on anything (commit stage executed before).
        """

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
        """Executes the first Execute Stage.

            It invokes the "tick" method of all ALUs to shift the instructions to the second stage of execution.
        """

        for alu in self.ALUs:
            alu.tick()

    def exec2(self):
        """Executes the second Execute Stage.

            Each ALU pops the executed instruction, the result, and the exception bit.
            If an instruction was executed, we update the entry in the ActiveList as DONE and set the exception bit.
            Subsequently, we update all entries of the IntegerQueue that rely on this physical register as operand to
            simulate the action of a forwarding path.
            Finally, we also set the physical register as not busy and write to the register file.
        """

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
                    if el.a_tag == instruction.dest_reg:
                        el.a_val = result
                        el.a_rdy = True
                    if el.b_tag == instruction.dest_reg:
                        el.b_val = result
                        el.b_rdy = True
                # Physical Register Update
                self.busy_bit[instruction.dest_reg] = False
                self.rf[instruction.dest_reg] = result

    def commit(self):
        """Executes the Commit Stage both in Standard and Exception-handling mode.

            Standard Operation:
                The commit stage tries to commit up to 4 DONE instructions by committing in order until it finds an
                instruction that generated an exception or that is not DONE.
                For each instruction that can be committed, it appends to the FreeList the old destination register that
                was mapped before issuing such instruction, and the entry is removed from the ActiveList.
                If an exception is spotted by checking at the "exception" bit of the ActiveListEntry, the ExceptionFlag is
                raised and all stages will be reset in the same cycle. 

            Exception Mode:
                Each cycle, the commit stage tries to roll-back up to 4 instructions at a time from the tail of the
                ActiveList, restoring the MapTable, appending to FreeList the physical registers, and clearing the
                BusyBit until all (AMONG WHICH THE INSTRUCTION RAISING THE EXCEPTION) have been rolled-back.

                The exception flag is left raised since nothing was mentioned in the assignment about that and we are
                supposed to stop the simulation upon exception.

        """

        if not self.exception_flag:
            removed_ids = []
            for i in range(min(4, len(self.active_list))):
                if not self.active_list[i].done:
                    break
                if self.active_list[i].exception:
                    # Handle Exception
                    self.exception_flag = True
                    self.e_pc = self.active_list[i].pc
                    for alu in self.ALUs:
                        alu.reset()
                    self.integer_queue = []
                    break
                else:
                    el = self.active_list[i]
                    removed_ids.append(i)
                    self.free_list.append(el.old_dest)
                    self.committed_instructions += 1
            removed_ids.sort(reverse=True)
            for id in removed_ids:
                self.active_list.pop(id)
            if self.committed_instructions == len(self.code) or (len(self.active_list) == 0 and self.pc >= len(self.code) and len(self.dir) == 0):
                return True
        else:
            curr_active_list_length = len(self.active_list)
            for i in range(min(4, curr_active_list_length)):
                # Roll-back Active List
                last_instr = self.active_list.pop()  # Grab last element
                curr_physical = self.map_table[last_instr.logical_dest]
                self.map_table[last_instr.logical_dest] = last_instr.old_dest
                self.free_list.append(curr_physical)
                self.busy_bit[curr_physical] = False  

            if len(self.active_list) == 0:
                # Exception has been handled
                self.exception_flag = False
                return True
        return False

    def log_state(self):
        out = dict()
        out["PC"] = self.pc
        out["PhysicalRegisterFile"] = self.rf.copy()
        out["DecodedPCs"] = [el.pc for el in self.dir]
        out["ExceptionPC"] = self.e_pc
        out["Exception"] = self.exception_flag
        out["RegisterMapTable"] = self.map_table.copy()
        out["FreeList"] = self.free_list.copy()
        out["BusyBitTable"] = self.busy_bit.copy()
        out["ActiveList"] = [{"Done": el.done, "Exception": el.exception, "LogicalDestination": el.logical_dest,
                              "OldDestination": el.old_dest, "PC": el.pc} for el in self.active_list]
        out["IntegerQueue"] = [{"DestRegister": el.dest_reg, "OpAIsReady": el.a_rdy, "OpARegTag": el.a_tag,
                                "OpAValue": el.a_val, "OpBIsReady": el.b_rdy, "OpBRegTag": el.b_tag,
                                "OpBValue": el.b_val,
                                "OpCode": el.opcode, "PC": el.pc} for el in self.integer_queue]
        self.state_log.append(out)

    def dump(self, filename):
        with open(filename, "w") as file:
            json.dump(self.state_log, file, indent=2)

    def check_asserts(self):
        """Checking that fixed length of internal data structures are not exceeded."""

        assert len(self.active_list) <= 32
        assert len(self.integer_queue) <= 32
        assert len(self.dir) <= 4

    def start(self, code, filename=""):
        """ Main simulation Loop.

            The simulation keeps running until either an exception is raised or all the code has been executed.
            At each cycle a backward pass of all stages is carried out from Commit to Fetch. This simplifies handling
            combinational paths and is an approach often used in simulating pipelines.
            At each cycle the CPU state is logged and when the simulation is finished it is dumped to file.
        """

        self.reset()
        self.code = code
        self.log_state()
        while not self.stop:
            self.stop = self.commit()
            self.exec2()
            self.exec1()
            self.issue()
            self.rename_dispatch()
            self.fetch_decode()
            self.check_asserts()
            self.log_state()
        if not len(self.code): # To handle output for empty program
            self.state_log.pop()
        if filename != "":
            self.dump(filename)
            print(f"Result File output to {filename}")
        else:
            return self.state_log


class Simulator:
    def __parse_input_file(self, filename):
        output = []
        with open(filename, "r") as file:
            for PC, instruction in enumerate(json.load(file)):
                opcode = instruction.split(" ")[0].strip()
                if opcode == "addi": opcode = "add"
                registers = instruction[instruction.find(" "):].split(",")
                destination_register = (registers[0].strip())
                operand_1 = (registers[1].strip())
                operand_2 = (registers[2].strip())
                output.append(Instruction(PC, opcode, destination_register, operand_1, operand_2))
        return output

    def __init__(self, filename):
        self.code = self.__parse_input_file(filename)
        self.filename = filename

    def run(self):
        cpu = CPU()
        cpu.start(self.code, f"out_{self.filename.split('/')[1]}")
