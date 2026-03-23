#!/usr/bin/env perl
use strict;
use warnings;
use Test::More;
use File::Temp qw(tempfile);
use IPC::Open3;
use Symbol 'gensym';

my $script = "$FindBin::Bin/timestamp_process_output.pl";

BEGIN { use FindBin; }
$script = "$FindBin::Bin/timestamp_process_output.pl";

# Helper to run the script and capture output
sub run_script {
    my @args = @_;
    my $err = gensym;
    my $pid = open3(my $in, my $out, $err, $script, @args);
    close $in;
    my @stdout = <$out>;
    my @stderr = <$err>;
    waitpid($pid, 0);
    my $exit_code = $? >> 8;
    return (\@stdout, \@stderr, $exit_code);
}

# Test 1: Basic stdout capture (no stamping by default)
subtest 'passes through stdout unchanged by default' => sub {
    my ($out, $err, $code) = run_script('echo', 'hello world');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 1, 'one line of output');
    is($out->[0], "hello world\n", 'output is unchanged');
};

# Test 2: Basic stderr capture (no stamping by default)
subtest 'passes through stderr unchanged by default' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'echo error >&2');
    is($code, 0, 'exit code is 0');
    is(scalar @$err, 1, 'one line of stderr');
    is($err->[0], "error\n", 'stderr is unchanged');
};

# Test 3: Mixed stdout and stderr (passthrough)
subtest 'passes through both stdout and stderr' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'echo out; echo err >&2');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 1, 'one line of stdout');
    is(scalar @$err, 1, 'one line of stderr');
    is($out->[0], "out\n", 'stdout passed through');
    is($err->[0], "err\n", 'stderr passed through');
};

# Test 4: Preserves exit code
subtest 'preserves child exit code' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'exit 42');
    is($code, 42, 'exit code preserved');
};

# Test 5: Logfile option (always stamped with elapsed time)
subtest 'writes to logfile when specified' => sub {
    my ($fh, $logfile) = tempfile(UNLINK => 1);
    close $fh;
    
    my ($out, $err, $code) = run_script('--logfile', $logfile, 'echo', 'logged');
    is($code, 0, 'exit code is 0');
    is($out->[0], "logged\n", 'stdout still passed through unchanged');
    
    open my $log, '<', $logfile or die "Cannot open $logfile: $!";
    my @lines = <$log>;
    close $log;
    
    is(scalar @lines, 1, 'one line in logfile');
    like($lines[0], qr/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\t[\d.]+\tSTDOUT\tlogged\n$/, 
         'logfile contains timestamp, elapsed, type, message');
};

# Test 6: Multiple lines (passthrough)
subtest 'handles multiple lines' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'echo one; echo two; echo three');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 3, 'three lines of output');
    is($out->[0], "one\n", 'first line');
    is($out->[1], "two\n", 'second line');
    is($out->[2], "three\n", 'third line');
};

# Test 7: No command shows usage
subtest 'shows usage without command' => sub {
    my ($out, $err, $code) = run_script();
    isnt($code, 0, 'non-zero exit code');
    like($err->[0], qr/Usage:/, 'shows usage message');
};

# Test 8: --stamp-stdout adds timestamps to stdout
subtest 'stamp-stdout adds timestamps to stdout' => sub {
    my ($out, $err, $code) = run_script('--stamp-stdout', 'echo', 'test message');
    is($code, 0, 'exit code is 0');
    my @fields = split /\t/, $out->[0];
    is(scalar @fields, 4, 'four tab-separated fields');
    like($fields[0], qr/^\d{4}-\d{2}-\d{2}T/, 'first field is timestamp');
    like($fields[1], qr/^[\d.]+$/, 'second field is elapsed time');
    is($fields[2], 'STDOUT', 'third field is stream type');
    like($fields[3], qr/^test message\n$/, 'fourth field is message');
};

# Test 9: --stamp-stderr adds timestamps to stderr
subtest 'stamp-stderr adds timestamps to stderr' => sub {
    my ($out, $err, $code) = run_script('--stamp-stderr', 'bash', '-c', 'echo error >&2');
    is($code, 0, 'exit code is 0');
    my @fields = split /\t/, $err->[0];
    is(scalar @fields, 4, 'four tab-separated fields');
    like($fields[0], qr/^\d{4}-\d{2}-\d{2}T/, 'first field is timestamp');
    like($fields[1], qr/^[\d.]+$/, 'second field is elapsed time');
    is($fields[2], 'STDERR', 'third field is stream type');
    like($fields[3], qr/^error\n$/, 'fourth field is message');
};

# Test 10: --stamp-stdout does not affect stderr
subtest 'stamp-stdout does not affect stderr' => sub {
    my ($out, $err, $code) = run_script('--stamp-stdout', 'bash', '-c', 'echo out; echo err >&2');
    is($code, 0, 'exit code is 0');
    like($out->[0], qr/^\d{4}-\d{2}-\d{2}T/, 'stdout is stamped');
    is($err->[0], "err\n", 'stderr is unchanged');
};

# Test 11: --stamp-stderr does not affect stdout
subtest 'stamp-stderr does not affect stdout' => sub {
    my ($out, $err, $code) = run_script('--stamp-stderr', 'bash', '-c', 'echo out; echo err >&2');
    is($code, 0, 'exit code is 0');
    is($out->[0], "out\n", 'stdout is unchanged');
    like($err->[0], qr/^\d{4}-\d{2}-\d{2}T/, 'stderr is stamped');
};

# Test 12: Both stamp flags together
subtest 'both stamp flags work together' => sub {
    my ($out, $err, $code) = run_script('--stamp-stdout', '--stamp-stderr', 'bash', '-c', 'echo out; echo err >&2');
    is($code, 0, 'exit code is 0');
    like($out->[0], qr/^\d{4}-\d{2}-\d{2}T.*\tSTDOUT\tout\n$/, 'stdout is stamped');
    like($err->[0], qr/^\d{4}-\d{2}-\d{2}T.*\tSTDERR\terr\n$/, 'stderr is stamped');
};

done_testing();
